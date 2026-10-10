"""Installable icon libraries (application/icon_libraries.py): what comes in is untrusted."""

import base64
import hashlib
import io
import json
import os
import tarfile
import zipfile

import pytest

from application import icon_libraries as icons

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M1 1h22" stroke="currentColor"/></svg>'


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _tgz(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        for name, data in files.items():
            raw = data.encode() if isinstance(data, str) else data
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            tf.addfile(info, io.BytesIO(raw))
    return buf.getvalue()


@pytest.fixture()
def icons_dir(tmp_path):
    return str(tmp_path / 'icons')


def _names(icons_dir, library):
    return sorted(f[:-4] for f in os.listdir(os.path.join(icons_dir, library)) if f.endswith('.svg'))


# --- SVG sanitizing ----------------------------------------------------------------------------

def test_a_plain_icon_survives():
    out = icons.sanitize_svg(SVG.encode())
    assert 'viewBox="0 0 24 24"' in out and 'd="M1 1h22"' in out and 'stroke="currentColor"' in out


@pytest.mark.parametrize('evil', [
    '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><path d="M0 0"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><path d="M0 0"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0" onclick="alert(1)"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><div>x</div></foreignObject><path d="M0 0"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><a href="javascript:alert(1)"><path d="M0 0"/></a></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><use href="https://evil.example/x.svg#a"/><path d="M0 0"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><style>@import url(https://evil.example/x.css);</style><path d="M0 0"/></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://evil.example/x.png"/><path d="M0 0"/></svg>',
])
def test_dangerous_parts_are_removed(evil):
    out = icons.sanitize_svg(evil.encode())
    assert out is not None
    lowered = out.lower()
    for bad in ('script', 'onload', 'onclick', 'foreignobject', 'javascript', 'evil.example', '@import', '<image', '<style', '<a '):
        assert bad not in lowered, bad


def test_references_to_the_same_document_stay_but_style_urls_do_not():
    out = icons.sanitize_svg(
        b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        b'<defs><linearGradient id="g"><stop offset="0"/></linearGradient></defs>'
        b'<path d="M0 0" fill="url(#g)" style="fill:url(https://evil.example/a)"/><use xlink:href="#g"/></svg>')
    assert 'fill="url(#g)"' in out and 'xlink:href="#g"' in out and 'evil.example' not in out and 'style=' not in out


@pytest.mark.parametrize('data', [
    b'', b'not xml', b'<html><body/></html>',
    b'<!DOCTYPE svg [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg">' + b'<g>' * 10 + b'</g>' * 9,   # not well-formed
])
def test_unusable_files_are_refused(data):
    assert icons.sanitize_svg(data) is None


def test_a_harmless_doctype_is_dropped_and_huge_files_refused():
    assert icons.sanitize_svg(b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">' + SVG.encode())
    assert icons.sanitize_svg(b'<svg xmlns="http://www.w3.org/2000/svg">' + b' ' * (icons.MAX_ICON_BYTES + 1) + b'</svg>') is None


# --- names -------------------------------------------------------------------------------------

def test_icon_names():
    assert icons.icon_name('Arrow_Up Right') == 'arrow-up-right'
    assert icons.icon_name('10k') == '10k'
    assert icons.icon_name('../x') == 'x'
    assert icons.icon_name('---') is None
    assert icons.icon_name('home-line', 'remix') == 'home'
    assert icons.icon_name('home-fill', 'remix') is None


# --- installing --------------------------------------------------------------------------------

def test_install_from_a_zip_with_folders(icons_dir):
    archive = _zip({'set/a/Home.svg': SVG, 'set/b/user_plus.svg': SVG, 'set/readme.txt': 'x', 'set/bad.svg': 'nope'})
    meta = icons.install(icons_dir, 'mine', archive, label='Mine', license='MIT')
    assert meta['count'] == 2 and meta['label'] == 'Mine'
    assert _names(icons_dir, 'mine') == ['home', 'user-plus']
    assert json.load(open(os.path.join(icons_dir, 'manifest.json'))) == {'mine': ['home', 'user-plus']}
    assert json.load(open(os.path.join(icons_dir, 'libraries.json')))['mine']['license'] == 'MIT'


def test_paths_in_an_archive_cannot_climb_out(icons_dir, tmp_path):
    archive = _zip({'../../escaped.svg': SVG, '/abs.svg': SVG, 'ok.svg': SVG})
    icons.install(icons_dir, 'safe', archive, label='Safe')
    assert _names(icons_dir, 'safe') == ['ok']  # the files with a climbing or absolute path are skipped
    assert not (tmp_path / 'escaped.svg').exists() and not os.path.exists('/abs.svg')


def test_a_tar_package_with_a_folder_filter_and_the_remix_rule(icons_dir):
    archive = _tgz({'package/icons/home-line.svg': SVG, 'package/icons/home-fill.svg': SVG,
                    'package/other/skip-line.svg': SVG, 'package/package.json': '{}'})
    icons.install(icons_dir, 'remixicon', archive, label='Remix', dirs=['icons'], rule='remix')
    assert _names(icons_dir, 'remixicon') == ['home']


def test_the_first_folder_that_has_icons_wins(icons_dir):
    archive = _tgz({'package/assets/regular/a.svg': SVG, 'package/assets/bold/b.svg': SVG})
    icons.install(icons_dir, 'phosphor', archive, label='P', dirs=['assets/regular', 'assets'])
    assert _names(icons_dir, 'phosphor') == ['a']


def test_nothing_usable_installs_nothing(icons_dir):
    with pytest.raises(icons.IconLibraryError, match='No usable'):
        icons.install(icons_dir, 'empty', _zip({'a.svg': 'bad', 'b.txt': 'x'}), label='E')
    assert not os.path.exists(os.path.join(icons_dir, 'empty'))
    assert [n for n in os.listdir(icons_dir) if n.startswith('.new-')] == []


def test_not_an_archive_and_bad_ids(icons_dir):
    with pytest.raises(icons.IconLibraryError, match='neither'):
        icons.install(icons_dir, 'x', b'plain text, no archive', label='X')
    for bad in ('', 'Upper', '../x', 'a b', 'x' * 41, '.hidden'):
        with pytest.raises(icons.IconLibraryError):
            icons.install(icons_dir, bad, _zip({'a.svg': SVG}), label='X')


def test_reinstall_replaces_and_remove_deletes(icons_dir):
    icons.install(icons_dir, 'lib', _zip({'a.svg': SVG, 'b.svg': SVG}), label='L')
    icons.install(icons_dir, 'lib', _zip({'c.svg': SVG}), label='L2')
    assert _names(icons_dir, 'lib') == ['c']
    assert [n for n in os.listdir(icons_dir) if n.startswith('.')] == []
    icons.remove(icons_dir, 'lib')
    assert json.load(open(os.path.join(icons_dir, 'manifest.json'))) == {}
    with pytest.raises(icons.IconLibraryError):
        icons.remove(icons_dir, 'lib')


def test_two_libraries_are_listed_together(icons_dir):
    icons.install(icons_dir, 'one', _zip({'a.svg': SVG}), label='One')
    icons.install(icons_dir, 'two', _zip({'b.svg': SVG, 'c.svg': SVG}), label='Two')
    assert {k: v['count'] for k, v in icons.installed(icons_dir).items()} == {'one': 1, 'two': 2}


# --- catalog and downloads ---------------------------------------------------------------------

def test_the_catalog_is_complete():
    assert [c['id'] for c in icons.CATALOG] == [
        'lucide', 'heroicons', 'phosphor', 'tabler', 'feather', 'material-symbols', 'bootstrap-icons', 'iconoir', 'remixicon']
    for entry in icons.CATALOG:
        assert icons.ID_PATTERN.match(entry['id'])
        assert entry['integrity'].startswith('sha512-') and entry['dirs']
        assert icons.catalog_url(entry).startswith('https://registry.npmjs.org/') and entry['version'] in icons.catalog_url(entry)


def _fake_download(monkeypatch, payload):
    monkeypatch.setattr(icons, 'download', lambda url, max_bytes=icons.MAX_DOWNLOAD_BYTES: payload)


def test_a_catalog_download_is_checked_against_the_pinned_checksum(icons_dir, monkeypatch):
    archive = _tgz({'package/icons/a.svg': SVG})
    entry = icons.catalog_entry('lucide')
    good = 'sha512-' + base64.b64encode(hashlib.sha512(archive).digest()).decode()
    monkeypatch.setitem(entry, 'integrity', good)
    _fake_download(monkeypatch, archive)
    meta = icons.install_from_catalog(icons_dir, 'lucide')
    assert meta['source'] == 'catalog' and meta['version'] == entry['version'] and _names(icons_dir, 'lucide') == ['a']
    # a tampered download is refused and the installed library stays
    _fake_download(monkeypatch, _tgz({'package/icons/evil.svg': SVG}))
    with pytest.raises(icons.IconLibraryError, match='checksum'):
        icons.install_from_catalog(icons_dir, 'lucide')
    assert _names(icons_dir, 'lucide') == ['a']


def test_download_goes_through_the_outbound_policy(monkeypatch):
    from application import net

    def blocked(url, **kwargs):
        raise net.OutboundBlocked('blocked: private address')
    monkeypatch.setattr(net, 'get', blocked)
    with pytest.raises(icons.IconLibraryError, match='blocked'):
        icons.download('http://192.168.0.5/icons.zip')


def test_install_from_a_url(icons_dir, monkeypatch):
    _fake_download(monkeypatch, _zip({'x/y.svg': SVG}))
    meta = icons.install_from_url(icons_dir, 'custom', 'https://example.org/i.zip', label='Custom', license='CC0')
    assert meta['source'] == 'url' and _names(icons_dir, 'custom') == ['y']
