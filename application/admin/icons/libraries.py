"""Installable icon libraries for the ``icon`` field handler.

DisplayHive ships no icons. An administrator installs libraries in Settings → Icon libraries, from the
list of known ones (downloaded from the npm registry, version and checksum pinned below) or from a ZIP
file / a download link of their own. Each library is a folder of SVG files::

    DATA_DIR/icons/
    ├── manifest.json        {library id: [icon names]}     read by the admin's icon picker
    ├── libraries.json       {library id: {label, license, …}}
    └── <library id>/<icon name>.svg      served at /static/icons/<library id>/<icon name>.svg

A stored icon value is ``<library id>/<icon name>``, the same as before libraries became installable, so
content keeps working once the library with that id is installed again.

Everything that comes in is untrusted: the screen puts an icon's markup straight into the page, so
:func:`sanitize_svg` keeps only a small allow-list of drawing elements and attributes (no script, no
event handlers, no external references), and archives are unpacked by hand with limits on size and count
and without ever trusting a path.
"""

import hashlib
import io
import json
import logging
import os
import re
import shutil
import tarfile
import threading
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from posixpath import normpath

logger = logging.getLogger(__name__)

MANIFEST = 'manifest.json'
LIBRARIES = 'libraries.json'
LIBRARY_META = '_library.json'

# Limits for one library (an archive from outside is never trusted to be reasonable).
MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024
MAX_UNPACKED_BYTES = 400 * 1024 * 1024
MAX_ICON_BYTES = 256 * 1024
MAX_ICONS = 40_000
ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]{0,39}$')
NAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9._-]{0,99}$')

# The libraries DisplayHive knows: where to get them and which folder of the package holds the icons.
# Versions and checksums are those of the frontends' former npm dependencies; a download is verified
# against `integrity` (the npm registry's sha512 of the tarball) before anything is unpacked.
CATALOG = [
    {
        'id': 'lucide', 'label': 'Lucide', 'license': 'ISC', 'homepage': 'https://lucide.dev',
        'package': 'lucide-static', 'version': '0.545.0',
        'integrity': 'sha512-2i81WNw3y+sN17gG75DKZbd43pGJREyoAQRK5IG8djCWhISoK6Ri1ovbKwOjFR+St2LHTQhu+EJygmUIWMotew==',
        'dirs': ['icons'], 'rule': 'kebab',
    },
    {
        'id': 'heroicons', 'label': 'Heroicons', 'license': 'MIT', 'homepage': 'https://heroicons.com',
        'package': 'heroicons', 'version': '2.2.0',
        'integrity': 'sha512-yOwvztmNiBWqR946t+JdgZmyzEmnRMC2nxvHFC90bF1SUttwB6yJKYeme1JeEcBfobdOs827nCyiWBS2z/brog==',
        'dirs': ['24/outline'], 'rule': 'kebab',
    },
    {
        'id': 'phosphor', 'label': 'Phosphor Icons', 'license': 'MIT', 'homepage': 'https://phosphoricons.com',
        'package': '@phosphor-icons/core', 'version': '2.1.1',
        'integrity': 'sha512-v4ARvrip4qBCImOE5rmPUylOEK4iiED9ZyKjcvzuezqMaiRASCHKcRIuvvxL/twvLpkfnEODCOJp5dM4eZilxQ==',
        'dirs': ['assets/regular', 'assets'], 'rule': 'kebab',
    },
    {
        'id': 'tabler', 'label': 'Tabler Icons', 'license': 'MIT', 'homepage': 'https://tabler.io/icons',
        'package': '@tabler/icons', 'version': '3.46.0',
        'integrity': 'sha512-f2RYFl3fzPwj5WO82x6en0dmkjefxEfOm16D1ByM6cj/McNiwOkL4VaPUoP9VVIrXAD9WnTSVFr70px703b//A==',
        'dirs': ['icons/outline', 'icons'], 'rule': 'kebab',
    },
    {
        'id': 'feather', 'label': 'Feather', 'license': 'MIT', 'homepage': 'https://feathericons.com',
        'package': 'feather-icons', 'version': '4.29.2',
        'integrity': 'sha512-0TaCFTnBTVCz6U+baY2UJNKne5ifGh7sMG4ZC2LoBWCZdIyPa+y6UiR4lEYGws1JOFWdee8KAsAIvu0VcXqiqA==',
        'dirs': ['dist/icons'], 'rule': 'kebab',
    },
    {
        'id': 'material-symbols', 'label': 'Material Symbols', 'license': 'Apache-2.0', 'homepage': 'https://fonts.google.com/icons',
        'package': '@material-symbols/svg-400', 'version': '0.35.2',
        'integrity': 'sha512-JP1x3+9BprQ0DeTJxyn8+Ta8lQJoJsmxxY+cFLVir+B6zywCsBva1kR4h66Nl47qXN14o0j+VsqsGmxh0US9kA==',
        'dirs': ['outlined', 'outline'], 'rule': 'kebab',
    },
    {
        'id': 'bootstrap-icons', 'label': 'Bootstrap Icons', 'license': 'MIT', 'homepage': 'https://icons.getbootstrap.com',
        'package': 'bootstrap-icons', 'version': '1.13.1',
        'integrity': 'sha512-ijombt4v6bv5CLeXvRWKy7CuM3TRTuPEuGaGKvTV5cz65rQSY8RQ2JcHt6b90cBBAC7s8fsf2EkQDldzCoXUjw==',
        'dirs': ['icons'], 'rule': 'kebab',
    },
    {
        'id': 'iconoir', 'label': 'Iconoir', 'license': 'MIT', 'homepage': 'https://iconoir.com',
        'package': 'iconoir', 'version': '7.11.1',
        'integrity': 'sha512-W3LG94l/LcZZv/Q7XZNFvQSkaQibS21B4pUytrIl+6Ue2FKAwhuuOo1+o7chjkWqhmYqboDUeUlQGXwPShCijw==',
        'dirs': ['icons/regular', 'icons'], 'rule': 'kebab',
    },
    {
        'id': 'remixicon', 'label': 'Remix Icon', 'license': 'Apache-2.0', 'homepage': 'https://remixicon.com',
        'package': 'remixicon', 'version': '4.9.1',
        'integrity': 'sha512-36gLSoujkabnCFZFDyP17VNh9piuBA/rsXUb4auSJWLGsHVXtmxLj/EM5FjaEAGnk8oIAj1Azob/DZ2N+90lAQ==',
        'dirs': ['icons'], 'rule': 'remix',
    },
]

_install_lock = threading.Lock()


class IconLibraryError(Exception):
    """The library cannot be installed; the message is meant for the administrator."""


# --- SVG ---------------------------------------------------------------------------------------

SVG_NS = 'http://www.w3.org/2000/svg'
XLINK_NS = 'http://www.w3.org/1999/xlink'

_ALLOWED_TAGS = {
    'svg', 'g', 'path', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'rect', 'defs', 'clipPath',
    'mask', 'linearGradient', 'radialGradient', 'stop', 'symbol', 'use', 'pattern', 'title', 'desc',
}
_ALLOWED_ATTRS = {
    'viewBox', 'width', 'height', 'preserveAspectRatio', 'version', 'xmlns', 'id', 'class', 'role',
    'aria-hidden', 'aria-label', 'focusable', 'd', 'fill', 'stroke', 'stroke-width', 'stroke-linecap',
    'stroke-linejoin', 'stroke-miterlimit', 'stroke-dasharray', 'stroke-dashoffset', 'stroke-opacity',
    'fill-opacity', 'fill-rule', 'clip-rule', 'opacity', 'transform', 'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y',
    'x1', 'x2', 'y1', 'y2', 'points', 'clip-path', 'mask', 'offset', 'stop-color', 'stop-opacity',
    'gradientUnits', 'gradientTransform', 'patternUnits', 'patternContentUnits', 'patternTransform',
    'clipPathUnits', 'maskUnits', 'maskContentUnits', 'fx', 'fy', 'spreadMethod', 'color', 'display',
    'visibility', 'vector-effect', 'shape-rendering',
}
_REFERENCE_ATTRS = {'fill', 'stroke', 'clip-path', 'mask'}
_MAX_ELEMENTS = 5000
_DOCTYPE = re.compile(rb'<!DOCTYPE[^>\[]*>', re.IGNORECASE)
_SAFE_STYLE = re.compile(r'^[a-zA-Z0-9#%.,:;\s()\-_]*$')
_SAFE_URL_REFERENCE = re.compile(r'^url\(\s*#[A-Za-z0-9_.:-]+\s*\)$')


def _local(tag):
    """(namespace, local name) of an ElementTree tag."""
    if tag.startswith('{'):
        ns, _, name = tag[1:].partition('}')
        return ns, name
    return '', tag


def _clean_attributes(element):
    cleaned = {}
    for key, value in element.attrib.items():
        ns, name = _local(key)
        if ns == XLINK_NS and name == 'href' or (not ns and name == 'href'):
            if value.startswith('#'):
                cleaned['{%s}href' % XLINK_NS] = value
            continue
        if ns or name.lower().startswith('on'):
            continue
        if name == 'style':
            if 'url(' not in value.lower() and _SAFE_STYLE.match(value) and 'javascript' not in value.lower():
                cleaned[name] = value
            continue
        if name not in _ALLOWED_ATTRS:
            continue
        lowered = value.strip().lower()
        if 'javascript:' in lowered or 'data:' in lowered or '<' in lowered:
            continue
        if 'url(' in lowered and not (name in _REFERENCE_ATTRS and _SAFE_URL_REFERENCE.match(value.strip())):
            continue
        cleaned[name] = value
    element.attrib.clear()
    element.attrib.update(cleaned)


def _clean_element(element, counter):
    counter[0] += 1
    if counter[0] > _MAX_ELEMENTS:
        raise ValueError('too many elements')
    for child in list(element):
        ns, name = _local(child.tag)
        if ns != SVG_NS or name not in _ALLOWED_TAGS:
            element.remove(child)
            continue
        child.tag = '{%s}%s' % (SVG_NS, name)
        _clean_element(child, counter)
    _clean_attributes(element)
    if element.text is not None and (len(element) or element.tag.split('}')[-1] not in ('title', 'desc')):
        element.text = None
    for child in element:
        child.tail = None


def sanitize_svg(data: bytes):
    """The icon as safe markup (text), or None if it is not a usable SVG.

    Keeps drawing elements and presentation attributes from a short allow-list; drops scripts, styles
    sheets, `<foreignObject>`, event handlers, links to anything but `#fragments`, and every foreign
    namespace (editor metadata). A DOCTYPE with an internal subset (entity tricks) is refused.
    """
    if not data or len(data) > MAX_ICON_BYTES:
        return None
    data = _DOCTYPE.sub(b'', data, count=1)
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        return None
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, ValueError):
        return None
    ns, name = _local(root.tag)
    if name != 'svg' or ns not in (SVG_NS, ''):
        return None
    root.tag = '{%s}svg' % SVG_NS
    try:
        _clean_element(root, [0])
    except (ValueError, RecursionError):
        return None
    ET.register_namespace('', SVG_NS)
    ET.register_namespace('xlink', XLINK_NS)
    return ET.tostring(root, encoding='unicode')


# --- names and archives ------------------------------------------------------------------------

def icon_name(stem: str, rule: str = 'kebab'):
    """The icon name for a file stem, or None if the file is not to be taken."""
    if rule == 'remix':
        # Every Remix icon ships as "-line" and "-fill": keep one so each name is unique.
        if not stem.endswith('-line'):
            return None
        stem = stem[: -len('-line')]
    name = re.sub(r'[^a-z0-9._-]+', '-', stem.replace('_', '-').lower()).strip('-.')
    return name if NAME_PATTERN.match(name) else None


def _safe_member_path(path: str):
    """The normalised relative path, or None for anything absolute or climbing out."""
    path = path.replace('\\', '/')
    if path.startswith('/') or re.match(r'^[A-Za-z]:', path):
        return None
    clean = normpath(path)
    if clean == '.' or clean.startswith('../') or clean == '..':
        return None
    return clean


def _iter_svg_files(archive: bytes):
    """Yield ``(relative path, bytes)`` of every ``.svg`` in a ZIP or (gzip) TAR archive."""
    total = 0
    if zipfile.is_zipfile(io.BytesIO(archive)):
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                path = _safe_member_path(info.filename)
                if info.is_dir() or path is None or not path.lower().endswith('.svg'):
                    continue
                if info.file_size > MAX_ICON_BYTES:
                    continue
                total += info.file_size
                if total > MAX_UNPACKED_BYTES:
                    raise IconLibraryError('The archive unpacks to more than %d MB.' % (MAX_UNPACKED_BYTES // 1024 // 1024))
                with zf.open(info) as f:
                    yield path, f.read(MAX_ICON_BYTES + 1)
        return
    try:
        tf = tarfile.open(fileobj=io.BytesIO(archive), mode='r:*')
    except tarfile.TarError:
        raise IconLibraryError('This is neither a ZIP nor a TAR archive.') from None
    with tf:
        members = sorted((m for m in tf.getmembers() if m.isfile()), key=lambda m: m.name)
        for member in members:
            path = _safe_member_path(member.name)
            if path is None or not path.lower().endswith('.svg') or member.size > MAX_ICON_BYTES:
                continue
            total += member.size
            if total > MAX_UNPACKED_BYTES:
                raise IconLibraryError('The archive unpacks to more than %d MB.' % (MAX_UNPACKED_BYTES // 1024 // 1024))
            f = tf.extractfile(member)
            if f is not None:
                yield path, f.read(MAX_ICON_BYTES + 1)


def _pick(files, dirs):
    """Restrict *files* to the first of the folders *dirs* (inside the package) that holds SVGs."""
    if not dirs:
        return files
    for folder in dirs:
        wanted = f'/{folder.strip("/")}/'
        chosen = [(p, d) for p, d in files if wanted in f'/{p}']
        if chosen:
            return chosen
    return []


# --- the library on disk -----------------------------------------------------------------------

def _read_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write_json(path, value):
    tmp = f'{path}.{uuid.uuid4().hex}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(value, f, separators=(',', ':'), sort_keys=True)
    os.replace(tmp, path)


def installed(icons_dir: str) -> dict:
    """{library id: metadata} of the installed libraries."""
    return _read_json(os.path.join(icons_dir, LIBRARIES), {})


def _rebuild_indexes(icons_dir: str):
    libraries, manifest = {}, {}
    for entry in sorted(os.listdir(icons_dir)):
        folder = os.path.join(icons_dir, entry)
        if entry.startswith('.') or not os.path.isdir(folder) or not ID_PATTERN.match(entry):
            continue
        meta = _read_json(os.path.join(folder, LIBRARY_META), None)
        if meta is None:
            continue
        names = sorted(f[:-4] for f in os.listdir(folder) if f.endswith('.svg'))
        meta['count'] = len(names)
        libraries[entry] = meta
        manifest[entry] = names
    _write_json(os.path.join(icons_dir, MANIFEST), manifest)
    _write_json(os.path.join(icons_dir, LIBRARIES), libraries)


def install(icons_dir: str, library_id: str, archive: bytes, *, label: str, license: str = '',
            homepage: str = '', source: str = 'upload', version: str = '', dirs=None, rule: str = 'kebab') -> dict:
    """Unpack *archive* as the library *library_id*, replacing an installed one. Returns its metadata."""
    if not ID_PATTERN.match(library_id or ''):
        raise IconLibraryError('The library id may contain lowercase letters, digits and dashes (at most 40).')
    label = (label or library_id).strip()[:80]
    with _install_lock:
        os.makedirs(icons_dir, exist_ok=True)
        staging = os.path.join(icons_dir, f'.new-{library_id}-{uuid.uuid4().hex[:8]}')
        os.makedirs(staging)
        try:
            names = set()
            for path, data in _pick(list(_iter_svg_files(archive)), dirs):
                name = icon_name(os.path.splitext(os.path.basename(path))[0], rule)
                if name is None or name in names:
                    continue
                svg = sanitize_svg(data)
                if svg is None:
                    continue
                with open(os.path.join(staging, f'{name}.svg'), 'w', encoding='utf-8') as f:
                    f.write(svg)
                names.add(name)
                if len(names) > MAX_ICONS:
                    raise IconLibraryError(f'More than {MAX_ICONS} icons.')
            if not names:
                raise IconLibraryError('No usable SVG icons were found in the archive.')
            meta = {
                'label': label, 'license': license.strip()[:80], 'homepage': homepage.strip()[:200],
                'source': source, 'version': version, 'count': len(names),
                'installed_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            }
            _write_json(os.path.join(staging, LIBRARY_META), meta)
            target = os.path.join(icons_dir, library_id)
            old = None
            if os.path.exists(target):
                old = os.path.join(icons_dir, f'.old-{library_id}-{uuid.uuid4().hex[:8]}')
                os.rename(target, old)
            os.rename(staging, target)
            if old:
                shutil.rmtree(old, ignore_errors=True)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        _rebuild_indexes(icons_dir)
    logger.info('Installed icon library %s (%d icons, source %s)', library_id, len(names), source)
    return meta


def remove(icons_dir: str, library_id: str) -> None:
    if not ID_PATTERN.match(library_id or ''):
        raise IconLibraryError('Unknown library.')
    with _install_lock:
        target = os.path.join(icons_dir, library_id)
        if not os.path.isdir(target):
            raise IconLibraryError('This library is not installed.')
        shutil.rmtree(target)
        _rebuild_indexes(icons_dir)
    logger.info('Removed icon library %s', library_id)


# --- downloads ---------------------------------------------------------------------------------

def catalog_entry(library_id: str):
    return next((c for c in CATALOG if c['id'] == library_id), None)


def catalog_url(entry: dict) -> str:
    """The npm registry's tarball address of a catalog entry."""
    base = entry['package'].split('/')[-1]
    return f"https://registry.npmjs.org/{entry['package']}/-/{base}-{entry['version']}.tgz"


def verify_integrity(data: bytes, integrity: str) -> bool:
    """npm's ``sha512-<base64>`` checksum of *data*."""
    import base64
    algorithm, _, expected = integrity.partition('-')
    if algorithm != 'sha512':
        return False
    return base64.b64encode(hashlib.sha512(data).digest()).decode() == expected


def download(url: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> bytes:
    """The body of *url*, through the outbound policy (no private networks unless an admin allowed them)."""
    from application import net
    try:
        response = net.get(url, timeout=60, max_bytes=max_bytes)
    except net.OutboundError as problem:
        raise IconLibraryError(str(problem)) from None
    except Exception as problem:
        raise IconLibraryError(f'The download failed: {problem}') from None
    if response.status_code != 200:
        raise IconLibraryError(f'The download failed: the server answered {response.status_code}.')
    return response.content


def install_from_catalog(icons_dir: str, library_id: str) -> dict:
    entry = catalog_entry(library_id)
    if entry is None:
        raise IconLibraryError('Unknown library.')
    data = download(catalog_url(entry))
    if not verify_integrity(data, entry['integrity']):
        raise IconLibraryError('The download does not match the checksum DisplayHive expects; nothing was installed.')
    return install(icons_dir, library_id, data, label=entry['label'], license=entry['license'],
                   homepage=entry['homepage'], source='catalog', version=entry['version'],
                   dirs=entry['dirs'], rule=entry['rule'])


def install_from_url(icons_dir: str, library_id: str, url: str, *, label: str, license: str = '') -> dict:
    return install(icons_dir, library_id, download(url), label=label, license=license, source='url')
