"""Aspect-ratio helpers and per-ratio container geometry / variant resolution."""

from types import SimpleNamespace

import pytest

from application.aspect_ratio import (
    BASE_RATIO, best_ratio, normalize_ratio, parse_ratio_list, ratio_value,
)
from application.admin.layouts.helper import (
    all_member_container_ids, container_geometry, containers_for_ratio,
    layout_ratios, resolve_layout_ratio,
)


@pytest.mark.parametrize('raw,expected', [
    ('16:9', '16:9'), (' 32 : 18 ', '16:9'), ('4:3', '4:3'), ('9:16', '9:16'), ('21:9', '21:9'), ('16:10', '16:10'),
    ('0:3', None), ('4', None), ('a:b', None), (None, None), (43, None), ('4:3:2', None),
])
def test_normalize_ratio(raw, expected):
    assert normalize_ratio(raw) == expected


def test_same_ratio():
    from application.aspect_ratio import same_ratio
    assert same_ratio('4:3', '8:6')
    assert not same_ratio('4:3', '3:4')


def test_ratio_value():
    assert ratio_value('4:3') == pytest.approx(4 / 3)


def test_parse_ratio_list_drops_invalid_base_and_duplicates():
    assert parse_ratio_list('["4:3", "8:6", "16:9", "x", "21:9"]') == ['4:3', '21:9']
    assert parse_ratio_list('not json') == []
    assert parse_ratio_list(None) == []
    assert parse_ratio_list(['9:16', '9:16']) == ['9:16']


def test_best_ratio_exact_and_closest():
    assert best_ratio('4:3', ['16:9', '4:3']) == '4:3'
    # 16:10 (1.6) is nearer 16:9 (1.78) than 4:3 (1.33)
    assert best_ratio('16:10', ['16:9', '4:3']) == '16:9'
    # portrait screen picks the portrait variant
    assert best_ratio('9:16', ['16:9', '3:4']) == '3:4'


def test_best_ratio_fallbacks():
    assert best_ratio('4:3', []) == BASE_RATIO
    assert best_ratio('garbage', ['4:3', '16:9']) == BASE_RATIO
    assert best_ratio(None, ['4:3']) == '4:3'


def test_best_ratio_equal_distance_prefers_base_then_first():
    # 1:1 is exactly as far from 4:3 as from 3:4: first listed wins
    assert best_ratio('1:1', ['3:4', '4:3']) == '3:4'
    assert best_ratio('1:1', ['4:3', '3:4']) == '4:3'
    # an exact duplicate of the target shape under another name still wins over base
    assert best_ratio('8:6', ['16:9', '4:3']) == '4:3'


def _container(cid, positions=()):
    return SimpleNamespace(
        id=cid, top=1.0, left=2.0, width=3.0, height=4.0,
        positions=[SimpleNamespace(aspect_ratio=r, top=t, left=l, width=w, height=h) for r, t, l, w, h in positions],
    )


def test_container_geometry_base_and_variant_with_fallback():
    c = _container(1, [('4:3', 10, 20, 30, 40)])
    assert container_geometry(c) == {'top': 1.0, 'left': 2.0, 'width': 3.0, 'height': 4.0}
    assert container_geometry(c, '4:3') == {'top': 10, 'left': 20, 'width': 30, 'height': 40}
    # no dedicated position at 21:9 -> falls back to the base columns
    assert container_geometry(c, '21:9') == {'top': 1.0, 'left': 2.0, 'width': 3.0, 'height': 4.0}


def _layout():
    a, b, c = _container(1), _container(2), _container(3)
    variation = SimpleNamespace(aspect_ratio='4:3', contentcontainers=[b])
    return SimpleNamespace(contentcontainers=[a, b], variations=[variation]), (a, b, c)


def test_layout_variant_helpers():
    layout, (a, b, c) = _layout()
    assert layout_ratios(layout) == ['16:9', '4:3']
    assert containers_for_ratio(layout) == [a, b]
    assert containers_for_ratio(layout, '4:3') == [b]
    assert containers_for_ratio(layout, '21:9') == []
    assert all_member_container_ids(layout) == {1, 2}
    assert resolve_layout_ratio(layout, '4:3') == '4:3'
    assert resolve_layout_ratio(layout, '16:10') == '16:9'
    assert resolve_layout_ratio(layout, None) == '16:9'


def test_combine_layout_containers_uses_ratio_geometry():
    from application.admin.content.helper import combine_layout_containers
    c = _container(1, [('4:3', 10, 20, 30, 40)])
    c.show_when_empty = True
    c.default_field_handler = None
    c.default_content = None
    base = combine_layout_containers([c], {}, ratio=BASE_RATIO)
    var = combine_layout_containers([c], {}, ratio='4:3')
    assert base['1']['top'] == 1.0
    assert var['1']['top'] == 10 and var['1']['width'] == 30
