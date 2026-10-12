"""FHD/4K/8K image renditions: sizes, never larger than the source, formats,
idempotence, removal and the backfill over a folder of existing uploads."""

import os

import pytest
from PIL import Image

from application import media_renditions as mr


def _make(path, size, fmt='PNG', mode='RGB'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new(mode, size, (200, 30, 30) if mode == 'RGB' else (200, 30, 30, 128)).save(path, fmt)


def _size(path):
    with Image.open(path) as im:
        return im.size


@pytest.fixture()
def dirs(tmp_path):
    media, rend = tmp_path / 'media', tmp_path / 'renditions'
    media.mkdir()
    rend.mkdir()
    return str(media), str(rend)


def test_5000px_source_gets_fhd_and_4k_but_not_8k(dirs):
    media, rend = dirs
    _make(os.path.join(media, 'a.png'), (5000, 3000))
    assert mr.render_renditions(os.path.join(media, 'a.png'), rend, 'a.png') == ['fhd', '4k']
    assert _size(mr.rendition_path(rend, 'fhd', 'a.png')) == (1920, 1152)
    assert _size(mr.rendition_path(rend, '4k', 'a.png')) == (3840, 2304)
    assert not os.path.exists(mr.rendition_path(rend, '8k', 'a.png'))


def test_never_rendered_larger_or_equal_to_the_source(dirs):
    media, rend = dirs
    _make(os.path.join(media, 'small.png'), (1000, 600))
    _make(os.path.join(media, 'exact.png'), (1920, 1080))
    assert mr.render_renditions(os.path.join(media, 'small.png'), rend, 'small.png') == []
    assert mr.render_renditions(os.path.join(media, 'exact.png'), rend, 'exact.png') == []
    assert os.listdir(rend) == []


def test_all_three_tiers_for_a_huge_source_keep_aspect_ratio(dirs):
    media, rend = dirs
    _make(os.path.join(media, 'big.png'), (9000, 4500))
    assert mr.render_renditions(os.path.join(media, 'big.png'), rend, 'big.png') == ['fhd', '4k', '8k']
    assert _size(mr.rendition_path(rend, '8k', 'big.png')) == (7680, 3840)


def test_portrait_images_are_measured_on_the_long_edge(dirs):
    media, rend = dirs
    _make(os.path.join(media, 'p.png'), (2000, 3000))
    assert mr.render_renditions(os.path.join(media, 'p.png'), rend, 'p.png') == ['fhd']
    assert _size(mr.rendition_path(rend, 'fhd', 'p.png')) == (1280, 1920)


def test_jpeg_stays_jpeg_and_png_keeps_transparency(dirs):
    media, rend = dirs
    _make(os.path.join(media, 'j.jpg'), (4000, 2000), 'JPEG')
    _make(os.path.join(media, 't.png'), (4000, 2000), 'PNG', 'RGBA')
    mr.render_renditions(os.path.join(media, 'j.jpg'), rend, 'j.jpg')
    mr.render_renditions(os.path.join(media, 't.png'), rend, 't.png')
    with Image.open(mr.rendition_path(rend, 'fhd', 'j.jpg')) as im:
        assert im.format == 'JPEG'
    with Image.open(mr.rendition_path(rend, 'fhd', 't.png')) as im:
        assert im.format == 'PNG' and im.mode == 'RGBA'


def test_idempotent_and_rerenders_when_source_is_newer(dirs):
    media, rend = dirs
    src = os.path.join(media, 'a.png')
    _make(src, (5000, 3000))
    assert mr.render_renditions(src, rend, 'a.png')
    assert mr.render_renditions(src, rend, 'a.png') == []
    os.utime(src, (os.path.getmtime(src) + 10, os.path.getmtime(src) + 10))
    assert mr.render_renditions(src, rend, 'a.png') == ['fhd', '4k']


def test_subfolders_and_removal(dirs):
    media, rend = dirs
    _make(os.path.join(media, 'logos', 'x.png'), (4000, 2000))
    mr.render_renditions(os.path.join(media, 'logos', 'x.png'), rend, 'logos/x.png')
    assert os.path.exists(mr.rendition_path(rend, 'fhd', 'logos/x.png'))
    mr.remove_renditions(rend, 'logos/x.png')
    assert not os.path.exists(mr.rendition_path(rend, 'fhd', 'logos/x.png'))
    assert not os.path.exists(mr.rendition_path(rend, '4k', 'logos/x.png'))


def test_ensure_all_backfills_existing_uploads_and_skips_missing_sources(dirs):
    media, rend = dirs
    _make(os.path.join(media, 'one.png'), (4000, 2000))
    _make(os.path.join(media, 'sub', 'two.jpg'), (2500, 1500), 'JPEG')
    _make(os.path.join(media, 'tiny.png'), (100, 100))
    stats = mr.ensure_all(['one.png', 'sub/two.jpg', 'tiny.png', 'gone.png'], media, rend)
    assert stats == {'checked': 3, 'created': 3, 'skipped_no_source': 1}  # one.png: fhd+4k, two.jpg: fhd


def test_concurrent_writes_of_the_same_rendition_dont_collide(tmp_path):
    """Two threads saving one rendition at once (backfill + "Sync previews")
    must both succeed and leave a complete file and no temp files behind."""
    import threading

    dest = str(tmp_path / 'fhd' / 'same.png')
    # Noise doesn't compress, so each save takes long enough for the threads
    # to actually overlap (zlib releases the GIL while compressing).
    img = Image.frombytes('RGB', (1920, 1080), os.urandom(1920 * 1080 * 3))
    errors = []

    for _ in range(3):
        start = threading.Barrier(6)

        def write():
            try:
                start.wait()
                mr._save(img, dest, 'PNG', {})
            except Exception as e:  # noqa: BLE001 — surfaced via the assert below
                errors.append(e)

        threads = [threading.Thread(target=write) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert errors == []
    assert _size(dest) == (1920, 1080)
    with Image.open(dest) as im:
        im.load()  # a file another thread wrote into half-way would fail here
    assert os.listdir(tmp_path / 'fhd') == ['same.png']


def test_renditions_are_removed_again_if_the_source_vanishes_while_rendering(dirs, monkeypatch):
    """e.g. an import wipes the media folder while a background backfill is mid-render."""
    media, rend = dirs
    src = os.path.join(media, 'gone.png')
    _make(src, (5000, 3000))
    real_save = mr._save

    def save_then_delete_source(*args, **kwargs):
        real_save(*args, **kwargs)
        if os.path.exists(src):
            os.remove(src)

    monkeypatch.setattr(mr, '_save', save_then_delete_source)
    assert mr.render_renditions(src, rend, 'gone.png') == []
    assert not os.path.exists(mr.rendition_path(rend, 'fhd', 'gone.png'))
    assert not os.path.exists(mr.rendition_path(rend, '4k', 'gone.png'))


def test_nothing_is_written_if_the_source_is_already_gone_when_saving_starts(dirs, monkeypatch):
    """A background job holds the opened image while an import wipes the folder."""
    media, rend = dirs
    src = os.path.join(media, 'wiped.png')
    _make(src, (5000, 3000))
    from PIL import ImageOps
    real_transpose = ImageOps.exif_transpose

    def transpose_then_wipe(img, *a, **k):
        out = real_transpose(img, *a, **k)
        os.remove(src)          # the folder is wiped after the image was opened
        return out

    monkeypatch.setattr(ImageOps, 'exif_transpose', transpose_then_wipe)
    assert mr.render_renditions(src, rend, 'wiped.png') == []
    assert not os.path.exists(os.path.join(rend, 'fhd', 'wiped.png'))
    assert not any(n.endswith('.png') or '.tmp-' in n for _r, _d, files in os.walk(rend) for n in files)
