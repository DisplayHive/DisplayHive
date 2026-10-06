"""Progress indicator config: cleaning of stored values and the payload sent to screens."""

import json
from types import SimpleNamespace

import pytest

from application.admin.designs.helper import (
    clean_indicator_color, clean_indicator_direction, clean_indicator_height, indicator_payload,
)


@pytest.mark.parametrize('value,expected', [
    ('#fff', '#fff'), ('#1a2b3c', '#1a2b3c'), ('red', 'red'), ('@default:abc-123', '@default:abc-123'),
    ('red; } body{display:none', None), ('url(x)', None), ('', None), (None, None), (5, None),
])
def test_clean_indicator_color(value, expected):
    assert clean_indicator_color(value) == expected


@pytest.mark.parametrize('value,expected', [
    (0.8, 0.8), ('2.5', 2.5), (0, 0.1), (-3, 0.1), (50, 10.0), ('x', None), (None, None), (float('nan'), None),
])
def test_clean_indicator_height(value, expected):
    assert clean_indicator_height(value) == expected


def test_clean_indicator_direction():
    assert clean_indicator_direction('ltr') == 'ltr'
    assert clean_indicator_direction('rtl') == 'rtl'
    assert clean_indicator_direction('up') is None


def _design(**kw):
    base = dict(
        indicator_enabled=False, indicator_color=None, indicator_height=None, indicator_direction=None,
        default_colors=json.dumps([{'id': 'brand', 'name': 'Brand', 'hex': '#336699'}]),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_payload_defaults_and_disabled_without_design():
    assert indicator_payload(None) == {'enabled': False, 'color': '#ffffff', 'height': 0.8, 'direction': 'ltr'}
    assert indicator_payload(_design()) == {'enabled': False, 'color': '#ffffff', 'height': 0.8, 'direction': 'ltr'}


def test_payload_resolves_palette_reference_and_uses_settings():
    p = indicator_payload(_design(indicator_enabled=True, indicator_color='@default:brand',
                                  indicator_height=1.5, indicator_direction='rtl'))
    assert p == {'enabled': True, 'color': '#336699', 'height': 1.5, 'direction': 'rtl'}


def test_payload_falls_back_when_palette_color_was_deleted():
    p = indicator_payload(_design(indicator_enabled=True, indicator_color='@default:gone'))
    assert p['color'] == '#ffffff'
