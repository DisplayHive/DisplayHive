"""Putting a plugin on disk (from a ZIP file, a download link or the catalog) and taking it off again.

An installed plugin lives in ``DATA_DIR/plugins/<id>/``, next to the ones bundled with the application. A
plugin's Python code runs with the rights of the server, so what comes in is checked as far as it can be:
the archive is unpacked by hand (limits on size and number of files, no path outside the folder, no
links), the manifest must be valid, and a download is verified against the SHA-256 checksum the catalog (or the
administrator) names before anything is unpacked. There is no signature: whoever can install a plugin
decides to trust its author.
"""

import hashlib
import io
import json
import logging
import shutil
import stat
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Optional

from application.plugins.manifest import MANIFEST_NAME, Manifest, PluginError, parse_manifest, read_manifest

logger = logging.getLogger(__name__)

MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
MAX_UNPACKED_BYTES = 200 * 1024 * 1024
MAX_FILES = 5000
MAX_CATALOG_BYTES = 2 * 1024 * 1024


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(name: str) -> Optional[PurePosixPath]:
    path = PurePosixPath(name.replace('\\', '/'))
    if path.is_absolute() or '..' in path.parts or not path.parts:
        return None
    return path


def _members(archive: zipfile.ZipFile) -> list:
    """The files to unpack as ``[(info, relative path)]``; ``PluginError`` for anything suspicious."""
    infos = [i for i in archive.infolist() if not i.is_dir()]
    if len(infos) > MAX_FILES:
        raise PluginError(f'The archive has more than {MAX_FILES} files.')
    if sum(i.file_size for i in infos) > MAX_UNPACKED_BYTES:
        raise PluginError('The archive is too large once unpacked.')
    out = []
    for info in infos:
        path = _safe_name(info.filename)
        if path is None:
            raise PluginError(f'The archive contains an unsafe path: {info.filename}')
        mode = info.external_attr >> 16
        kind = stat.S_IFMT(mode)            # zero when the tool only stored permission bits
        if kind and kind != stat.S_IFREG:
            raise PluginError(f'The archive contains a link or special file: {info.filename}')
        if path.parts[0] in ('__MACOSX',) or path.name == '.DS_Store':
            continue
        out.append((info, path))
    return out


def _strip_root(members: list) -> list:
    """The plugin may sit at the archive root or inside one folder (what "zip this folder" produces)."""
    if any(len(p.parts) == 1 and p.name == MANIFEST_NAME for _, p in members):
        return members
    roots = {p.parts[0] for _, p in members}
    if len(roots) == 1 and any(len(p.parts) == 2 and p.name == MANIFEST_NAME for _, p in members):
        return [(i, PurePosixPath(*p.parts[1:])) for i, p in members]
    raise PluginError(f'The archive contains no {MANIFEST_NAME}.')


def install_zip(data: bytes, installed_dir: Path, *, host_version: str = '', sha256: str = '',
                expected_id: str = '') -> Manifest:
    """Unpack *data* (a ZIP file) as a plugin into *installed_dir*. Returns its manifest.

    An existing installed version of the same plugin is replaced. ``PluginError`` leaves the installed
    plugins as they were.
    """
    from application.plugins.manifest import host_accepts, PLUGIN_API
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise PluginError('The file is too large.')
    if sha256 and sha256_of(data) != sha256.strip().lower():
        raise PluginError('The file does not match the checksum; nothing was installed.')
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise PluginError('This is not a ZIP file.') from None
    with archive:
        members = _strip_root(_members(archive))
        manifest_info = next(i for i, p in members if p.parts == (MANIFEST_NAME,))
        try:
            manifest = parse_manifest(json.loads(archive.read(manifest_info).decode('utf-8')))
        except (ValueError, UnicodeDecodeError) as problem:
            raise PluginError(f'{MANIFEST_NAME} cannot be read: {problem}') from None
        if expected_id and manifest.id != expected_id:
            raise PluginError(f'The archive contains {manifest.id}, not {expected_id}.')
        if manifest.plugin_api != PLUGIN_API:
            raise PluginError(f'{manifest.id} is built for plugin API {manifest.plugin_api}; this DisplayHive offers {PLUGIN_API}.')
        if not host_accepts(manifest.requires_host, host_version):
            raise PluginError(f'{manifest.id} needs DisplayHive {manifest.requires_host} (this is {host_version}).')
        from application.plugins import packages
        lacking = packages.unmet(manifest.requires_python_packages)
        if lacking:
            raise PluginError(f'{manifest.id} needs the Python package(s) {", ".join(lacking)}, which this server does not have; nothing was installed.')
        installed_dir = Path(installed_dir)
        installed_dir.mkdir(parents=True, exist_ok=True)
        staging = installed_dir / f'.staging-{uuid.uuid4().hex}'
        try:
            total = 0
            for info, path in members:
                target = staging.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, open(target, 'wb') as out:
                    while chunk := source.read(1 << 20):
                        total += len(chunk)
                        if total > MAX_UNPACKED_BYTES:
                            raise PluginError('The archive is too large once unpacked.')
                        out.write(chunk)
            checked = read_manifest(staging)      # what was written is what was read
            final = installed_dir / checked.id
            previous = None
            if final.exists():
                previous = installed_dir / f'.old-{uuid.uuid4().hex}'
                final.rename(previous)
            try:
                staging.rename(final)
            except OSError:
                if previous is not None:
                    previous.rename(final)
                raise
            if previous is not None:
                shutil.rmtree(previous, ignore_errors=True)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    logger.info('Installed plugin %s %s', manifest.id, manifest.version)
    return read_manifest(installed_dir / manifest.id)


def remove(installed_dir: Path, plugin_id: str) -> None:
    """Delete an installed plugin's files. Bundled plugins have none here and cannot be removed."""
    folder = Path(installed_dir) / plugin_id
    if not folder.is_dir() or folder.resolve().parent != Path(installed_dir).resolve():
        raise PluginError(f'{plugin_id} is not an installed plugin (bundled plugins can only be switched off).')
    shutil.rmtree(folder)
    logger.info('Removed plugin %s', plugin_id)


# --- Downloads and the catalog ------------------------------------------------------------------

def download(url: str, max_bytes: int = MAX_DOWNLOAD_BYTES) -> bytes:
    """The body of *url*, through the outbound policy (no private networks unless an administrator allowed them)."""
    from application.security import net
    try:
        response = net.get(url, timeout=60, max_bytes=max_bytes)
    except net.OutboundError as problem:
        raise PluginError(str(problem)) from None
    except Exception as problem:
        raise PluginError(f'The download failed: {problem}') from None
    if response.status_code != 200:
        raise PluginError(f'The download failed: the server answered {response.status_code}.')
    return response.content


def install_url(url: str, installed_dir: Path, *, sha256: str, host_version: str = '', expected_id: str = '') -> Manifest:
    """Download *url* and install it. A checksum is required: a link alone proves nothing."""
    if not (sha256 or '').strip():
        raise PluginError('Enter the SHA-256 checksum of the file.')
    return install_zip(download(url), installed_dir, host_version=host_version, sha256=sha256, expected_id=expected_id)


def fetch_catalog(url: str) -> list:
    """The entries of the catalog at *url*: ``[{id, name, version, description, url, sha256, …}]``.

    The catalog is a JSON file ``{"plugins": [...]}``; entries that are not valid are dropped."""
    if not url:
        return []
    try:
        data = json.loads(download(url, MAX_CATALOG_BYTES).decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        raise PluginError('The catalog is not valid JSON.') from None
    entries = data.get('plugins') if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise PluginError('The catalog has no "plugins" list.')
    out = []
    for e in entries:
        if (isinstance(e, dict) and all(isinstance(e.get(k), str) and e.get(k) for k in ('id', 'name', 'version', 'url', 'sha256'))):
            out.append({k: e.get(k, '') for k in ('id', 'name', 'version', 'description', 'url', 'sha256', 'author', 'license', 'homepage', 'kind')})
    return out
