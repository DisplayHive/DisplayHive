"""Tests for application/admin/designs/helper.py's pure functions:
gradient_css_value and the resolve_default_color(_deep) family.

Both accept a duck-typed `design`/`gradient`-like object rather than a real
ORM row — a plain namespace with the accessed attributes is enough.
"""

import json
from types import SimpleNamespace

import pytest

from application.admin.designs.helper import (
    gradient_css_value,
    resolve_default_color,
    resolve_default_colors_deep,
)


def _design(colors):
    return SimpleNamespace(default_colors=json.dumps(colors))


def _gradient(**overrides):
    defaults = dict(
        stops=json.dumps([
            {'color': '#ff0000', 'position': 0, 'opacity': 100},
            {'color': '#0000ff', 'position': 100, 'opacity': 100},
        ]),
        repeating=False,
        type='linear',
        angle=45,
        position_x=None,
        position_y=None,
        shape=None,
        size=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# --- resolve_default_color ------------------------------------------------------


def test_resolve_default_color_passes_through_literal_value():
    design = _design([{'id': '1', 'hex': '#123456'}])
    assert resolve_default_color(design, '#abcdef') == '#abcdef'


def test_resolve_default_color_passes_through_non_string():
    design = _design([])
    assert resolve_default_color(design, None) is None


def test_resolve_default_color_resolves_reference():
    design = _design([{'id': '7', 'hex': '#00ff00'}])
    assert resolve_default_color(design, '@default:7') == '#00ff00'


def test_resolve_default_color_deleted_id_resolves_to_empty_string():
    design = _design([{'id': '1', 'hex': '#123456'}])
    assert resolve_default_color(design, '@default:missing') == ''


def test_resolve_default_color_malformed_json_degrades_to_empty():
    design = SimpleNamespace(default_colors='not json')
    assert resolve_default_color(design, '@default:1') == ''


# --- resolve_default_colors_deep ------------------------------------------------


def test_resolve_default_colors_deep_resolves_nested_dict():
    design = _design([{'id': '1', 'hex': '#111111'}])
    value = {'background': '@default:1', 'size': 10}
    resolved = resolve_default_colors_deep(value, design)
    assert resolved == {'background': '#111111', 'size': 10}


def test_resolve_default_colors_deep_resolves_list_of_strings():
    design = _design([{'id': '1', 'hex': '#111111'}, {'id': '2', 'hex': '#222222'}])
    value = ['@default:1', '@default:2', 'literal']
    assert resolve_default_colors_deep(value, design) == ['#111111', '#222222', 'literal']


def test_resolve_default_colors_deep_leaves_non_string_scalars_untouched():
    design = _design([])
    assert resolve_default_colors_deep(42, design) == 42
    assert resolve_default_colors_deep(True, design) is True
    assert resolve_default_colors_deep(None, design) is None


# --- gradient_css_value ----------------------------------------------------------


def test_gradient_css_value_linear():
    g = _gradient(type='linear', angle=90)
    value = gradient_css_value(g)
    assert value == 'linear-gradient(90deg, #ff0000 0%, #0000ff 100%)'


def test_gradient_css_value_radial():
    g = _gradient(type='radial', shape='circle', size='closest-side', position_x=25, position_y=75)
    value = gradient_css_value(g)
    assert value == 'radial-gradient(circle closest-side at 25% 75%, #ff0000 0%, #0000ff 100%)'


def test_gradient_css_value_conic():
    g = _gradient(type='conic', angle=180, position_x=10, position_y=20)
    value = gradient_css_value(g)
    assert value == 'conic-gradient(from 180deg at 10% 20%, #ff0000 0%, #0000ff 100%)'


def test_gradient_css_value_repeating_prefix():
    g = _gradient(type='linear', repeating=True)
    assert gradient_css_value(g).startswith('repeating-linear-gradient(')


def test_gradient_css_value_fewer_than_two_stops_returns_empty():
    g = _gradient(stops=json.dumps([{'color': '#ff0000', 'position': 0}]))
    assert gradient_css_value(g) == ''


def test_gradient_css_value_no_gradient_returns_empty():
    assert gradient_css_value(None) == ''


def test_gradient_css_value_blank_stops_returns_empty():
    g = _gradient(stops='')
    assert gradient_css_value(g) == ''


def test_gradient_css_value_malformed_stops_json_returns_empty():
    g = _gradient(stops='not json')
    assert gradient_css_value(g) == ''


def test_gradient_css_value_alpha_hex_for_partial_opacity():
    g = _gradient(stops=json.dumps([
        {'color': '#ff0000', 'position': 0, 'opacity': 50},
        {'color': '#0000ff', 'position': 100, 'opacity': 100},
    ]))
    value = gradient_css_value(g)
    # 50% opacity -> alpha byte round(0.5 * 255) = 128 = 0x80
    assert '#ff000080' in value
    # Fully opaque stops stay 6-digit (no alpha channel appended).
    assert '#0000ff ' in value and '#0000ffff' not in value


def test_gradient_css_value_unknown_type_returns_empty():
    g = _gradient(type='not-a-real-gradient-type')
    assert gradient_css_value(g) == ''
