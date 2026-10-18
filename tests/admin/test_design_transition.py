"""Transition settings of a Design: cleaning of stored values and the payload sent to screens."""

from types import SimpleNamespace

import pytest

from application.admin.designs.helper import (
    clean_transition, clean_transition_direction, clean_transition_duration, clean_transition_scope, clean_transition_stagger, transition_payload,
)


@pytest.mark.parametrize('value,expected', [
    ('fade', 'fade'), ('zoom-in', 'zoom-in'), ('flip', 'flip'), ('random', 'random'), ('random-container', 'random-container'),
    ('random-light', 'random-light'), ('random-medium', 'random-medium'), ('random-container-light', 'random-container-light'),
    ('random-container-medium', 'random-container-medium'),
    ('explode', None), ('none', None), ('', None), (None, None), (5, None),
])
def test_clean_transition(value, expected):
    assert clean_transition(value) == expected


def test_clean_transition_direction():
    assert [clean_transition_direction(d) for d in ('left', 'right', 'up', 'down')] == ['left', 'right', 'up', 'down']
    assert clean_transition_direction('sideways') is None


@pytest.mark.parametrize('value,expected', [
    (600, 600), ('450', 450), (10, 100), (-5, 100), (99999, 5000), ('x', None), (None, None), (float('nan'), None),
])
def test_clean_transition_duration(value, expected):
    assert clean_transition_duration(value) == expected


def test_payload_defaults_to_no_transition():
    assert transition_payload(None) == {'type': 'none', 'direction': 'left', 'duration_ms': 600, 'sequential': False, 'unchanged': False, 'scope': 'container', 'stagger': 'none'}
    assert transition_payload(SimpleNamespace(transition=None, transition_direction=None, transition_duration_ms=None)) == {
        'type': 'none', 'direction': 'left', 'duration_ms': 600, 'sequential': False, 'unchanged': False, 'scope': 'container', 'stagger': 'none',
    }


def test_payload_uses_the_settings_and_drops_what_is_invalid():
    design = SimpleNamespace(transition='slide', transition_direction='up', transition_duration_ms=900, transition_sequential=True,
                            transition_unchanged=True,
                            transition_scope='slide', transition_stagger='centre-out')
    assert transition_payload(design) == {
        'type': 'slide', 'direction': 'up', 'duration_ms': 900, 'sequential': True, 'unchanged': True, 'scope': 'slide',
        'stagger': 'centre-out',
    }
    bad = SimpleNamespace(transition='<script>', transition_direction='x', transition_duration_ms='y')
    assert transition_payload(bad) == {'type': 'none', 'direction': 'left', 'duration_ms': 600, 'sequential': False, 'unchanged': False, 'scope': 'container', 'stagger': 'none'}


def test_clean_transition_scope():
    assert clean_transition_scope('slide') == 'slide' and clean_transition_scope('container') == 'container'
    assert clean_transition_scope('screen') is None and clean_transition_scope(None) is None


def test_clean_transition_stagger():
    assert [clean_transition_stagger(v) for v in ('order', 'top-bottom', 'left-right', 'centre-out', 'random')] == [
        'order', 'top-bottom', 'left-right', 'centre-out', 'random']
    assert clean_transition_stagger('none') is None and clean_transition_stagger('x') is None


def test_the_types_match_what_the_screen_knows():
    """The list the server accepts is the list of the screen client (frontends/screen/ts/screen/transitions.ts)."""
    import re
    from pathlib import Path

    from application.admin.designs.helper import TRANSITION_TYPES
    source = (Path(__file__).parents[2] / 'frontends/screen/ts/screen/transitions.ts').read_text(encoding='utf-8')
    concrete = re.search(r'CONCRETE_TYPES = \[(.*?)\] as const', source, re.S).group(1)
    random_types = re.search(r'RANDOM_TYPES = \[(.*?)\] as const', source, re.S).group(1)
    in_screen = re.findall(r'"([a-z-]+)"', concrete) + re.findall(r'"([a-z-]+)"', random_types)
    assert sorted(TRANSITION_TYPES) == sorted(in_screen)
