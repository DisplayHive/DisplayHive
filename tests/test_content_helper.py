"""Tests for application/admin/content/helper.py's render_content_fields —
specifically the locked/hidden option-flag override enforcement (the actual
security boundary preventing a client from overwriting a Contenttype-locked
field's value). Uses duck-typed stub TagConfig objects rather than real ORM
rows, per the function's own documented contract (field_name, field_handler,
contentcontainer_id, option_flags, default_value, contentcontainer).
"""

import json
from types import SimpleNamespace

from application.admin.content.helper import render_content_fields


def _tagconfig(field_name='title', field_handler='textklein', contentcontainer_id=1,
                option_flags=None, default_value=None, contentcontainer=None):
    return SimpleNamespace(
        field_name=field_name,
        field_handler=field_handler,
        contentcontainer_id=contentcontainer_id,
        option_flags=json.dumps(option_flags) if option_flags is not None else None,
        default_value=json.dumps(default_value) if default_value is not None else None,
        contentcontainer=contentcontainer,
    )


def test_locked_field_ignores_client_value_uses_preset():
    tc = _tagconfig(
        option_flags={'title': {'locked': True}},
        default_value={'title': 'Preset Value'},
    )
    result = render_content_fields([tc], json.dumps({'title': 'Client Value'}))
    assert result['1'] == 'Preset Value'


def test_hidden_field_ignores_client_value_uses_preset():
    tc = _tagconfig(
        option_flags={'title': {'hidden': True}},
        default_value={'title': 'Preset Value'},
    )
    result = render_content_fields([tc], json.dumps({'title': 'Client Value'}))
    assert result['1'] == 'Preset Value'


def test_unlocked_field_passes_through_client_value():
    tc = _tagconfig(option_flags=None, default_value=None)
    result = render_content_fields([tc], json.dumps({'title': 'Client Value'}))
    assert result['1'] == 'Client Value'


def test_locked_flag_without_matching_preset_key_leaves_client_value():
    # The preset dict has no 'title' entry, so the override loop's
    # `key in preset` guard skips it — the client value passes through.
    tc = _tagconfig(
        option_flags={'title': {'locked': True}},
        default_value={},
    )
    result = render_content_fields([tc], json.dumps({'title': 'Client Value'}))
    assert result['1'] == 'Client Value'


def test_missing_value_and_no_container_falls_back_to_empty_string():
    tc = _tagconfig(contentcontainer=None)
    result = render_content_fields([tc], json.dumps({}))
    assert result['1'] == ''


def test_field_with_no_container_assigned_is_skipped():
    tc = _tagconfig(contentcontainer_id=None)
    result = render_content_fields([tc], json.dumps({'title': 'Client Value'}))
    assert result == {}


def test_malformed_serialized_input_degrades_to_empty_context():
    tc = _tagconfig(default_value={'title': 'irrelevant'})
    result = render_content_fields([tc], 'not valid json')
    assert result['1'] == ''


def test_malformed_option_flags_json_does_not_crash():
    tc = SimpleNamespace(
        field_name='title', field_handler='textklein', contentcontainer_id=1,
        option_flags='not valid json', default_value=None, contentcontainer=None,
    )
    result = render_content_fields([tc], json.dumps({'title': 'Client Value'}))
    assert result['1'] == 'Client Value'


def test_html_special_characters_are_escaped():
    tc = _tagconfig()
    result = render_content_fields([tc], json.dumps({'title': '<script>alert(1)</script>'}))
    assert '<script>' not in result['1']
    assert '&lt;script&gt;' in result['1']
