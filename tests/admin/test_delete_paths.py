"""Deleting a parent row, through the handler the admin uses, with children attached.

The policy (docs/developer/architecture.md → "Deleting rows"): whoever deletes cleans up, and the database must never be
left with a row that points at a row that is gone. Many foreign keys have no ``ON DELETE`` rule, so the handlers (or the
ORM relationships) are what protects them: this test deletes each kind of parent with children and checks, afterwards,
every foreign key of every table. A handler may refuse ("still in use"); it may not fail with an error or leave orphans.
"""

import json
from datetime import datetime

import pytest
import sqlalchemy as sa

from application.models import (
    AdminUser, AdminUserIdentity, AdminUserLogin, AuthProvider, ContainerPosition, ContentContainer, ContentElement,
    Contenttype, Design, DesignContainerStyle, DesignGlobalStyle, DesignGradient, Device, Gradient, Group, GroupRight,
    Layout, RightDefinition, Screen, Screengroup, TagConfig, UserGroup, UserRight, db,
)
from tests.admin.test_admin_actions import superadmin_client  # noqa: F401  (fixture)


def orphans(session) -> set:
    """``{"child.column -> parent.column": rows}`` for every foreign key whose rows point at nothing."""
    found = set()
    for table in db.metadata.sorted_tables:
        for fk in table.foreign_keys:
            parent_column, child_column = fk.column, fk.parent
            parent = parent_column.table.alias('parent')              # also for a table that points at itself
            query = (sa.select(sa.func.count())
                     .select_from(table.outerjoin(parent, child_column == parent.c[parent_column.name]))
                     .where(child_column.is_not(None), parent.c[parent_column.name].is_(None)))
            count = session.execute(query).scalar()
            if count:
                found.add(f'{table.name}.{child_column.name} -> {parent_column.table.name}.{parent_column.name}: {count}')
    return found


def delete(client, db_session, event, data, refused=False):
    """Call a delete handler; it must answer cleanly and leave no orphans. ``refused=True``: it must say "still in use";
    ``refused=None``: either is fine."""
    before = orphans(db_session)
    ack = client.emit(event, data, callback=True)
    assert isinstance(ack, dict), f'{event} gave no answer'
    assert 'error_ref' not in ack, f'{event} failed unexpectedly: {ack}'
    if refused is None:
        assert ack.get('success') or ack.get('error'), ack
    elif refused:
        assert ack.get('success') is False and ack.get('error'), ack
    else:
        assert ack.get('success') or 'data' in ack or 'providers' in ack, ack
    db_session.expire_all()
    assert orphans(db_session) <= before, f'{event} left rows pointing at nothing: {sorted(orphans(db_session) - before)}'
    return ack


def now():
    return datetime(2026, 1, 1)


def screen_with_everything(db_session, name):
    screen = Screen(name=name, lastseen=now(), active=True)
    group = Screengroup(name=f'{name}-group')
    group.screens.append(screen)
    element = ContentElement(title=f'{name}-content', html='', duration=1, active=True, serialized_input='{}')
    group.content_elements.append(element)
    db_session.add_all([screen, group, element])
    db_session.flush()
    device = Device(devicekey=f'key-{name}', name=f'{name}-device', screen_id=screen.id)
    db_session.add(device)
    db_session.commit()
    return screen, group, element, device


def test_deleting_a_screen_a_group_a_content_element_or_a_device(db_session, superadmin_client):
    screen, group, element, device = screen_with_everything(db_session, 'dp1')
    delete(superadmin_client, db_session, 'displayhive:screens:cts:delete_screen', {'screen_id': screen.id}, refused=True)    # a device uses it
    assert db_session.get(Screen, screen.id) is not None
    delete(superadmin_client, db_session, 'displayhive:devices:cts:delete_device', {'device_id': device.id})
    delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_content_element', {'content_element_id': element.id})
    delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_screengroup', {'screengroup_id': group.id}, refused=True)   # the screen is in it
    delete(superadmin_client, db_session, 'displayhive:screens:cts:delete_screen', {'screen_id': screen.id})
    assert db_session.get(Screen, screen.id) is None


def test_deleting_a_group_that_still_has_screens_and_content(db_session, superadmin_client):
    screen, group, element, device = screen_with_everything(db_session, 'dp2')
    delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_screengroup', {'screengroup_id': group.id}, refused=True)
    assert db_session.get(Screengroup, group.id) is not None                  # not deleted, and nothing half-deleted
    assert db_session.get(Screen, screen.id) is not None and db_session.get(ContentElement, element.id) is not None


def layout_with_everything(db_session, name):
    layout = Layout(name=f'{name}-layout')
    container = ContentContainer(name=f'{name}-container', order=1)
    layout.contentcontainers.append(container)
    contenttype = Contenttype(name=f'{name}-type', layout=layout)
    db_session.add_all([layout, container, contenttype])
    db_session.flush()
    db_session.add(TagConfig(contenttype_id=contenttype.id, field_name=f'{name}-container', field_handler='textklein',
                             contentcontainer_id=container.id, order=0))
    db_session.add(ContainerPosition(contentcontainer_id=container.id, aspect_ratio='4:3', top=0, left=0, width=1, height=1))
    element = ContentElement(title=f'{name}-el', html='', duration=1, active=True, serialized_input='{}', contenttype=contenttype)
    design = Design(name=f'{name}-design', html='', css='')
    db_session.add_all([element, design])
    db_session.flush()
    db_session.add(DesignContainerStyle(design_id=design.id, contentcontainer_id=container.id, property='color', value='red'))
    db_session.commit()
    return layout, container, contenttype, element, design


@pytest.mark.parametrize('victim', ['contenttype', 'layout', 'container'])
def test_deleting_the_parts_of_a_layout_in_any_order(db_session, superadmin_client, victim):
    layout, container, contenttype, element, design = layout_with_everything(db_session, f'dp-{victim}')
    ids = {'contenttype': contenttype.id, 'layout': layout.id, 'container': container.id}
    events = {'contenttype': 'displayhive:admin:cts:delete_contenttype', 'layout': 'displayhive:admin:cts:delete_layout',
              'container': 'displayhive:admin:cts:delete_container'}
    delete(superadmin_client, db_session, events[victim], {'id': ids[victim]}, refused=None)          # in use: refused, or done
    delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_content_element', {'content_element_id': element.id})
    for other in ('contenttype', 'layout', 'container'):
        delete(superadmin_client, db_session, events[other], {'id': ids[other]}, refused=None)
    delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_design', {'id': design.id})
    assert db_session.get(Contenttype, contenttype.id) is None and db_session.get(Layout, layout.id) is None


def test_deleting_a_design_with_gradients_and_styles_and_a_gradient_in_use(db_session, superadmin_client):
    design = Design(name='dp-design', html='', css='')
    gradient = Gradient(name='dp-gradient', type='linear', stops='[]')
    other = Gradient(name='dp-unused', type='linear', stops='[]')
    container = ContentContainer(name='dp-gc', order=1)
    db_session.add_all([design, gradient, other, container])
    db_session.flush()
    db_session.add_all([DesignGradient(design_id=design.id, gradient_id=gradient.id, order=0),
                        DesignContainerStyle(design_id=design.id, contentcontainer_id=container.id, property='color', value='x'),
                        DesignGlobalStyle(design_id=design.id, property='color', value='x')])
    db_session.commit()
    delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_gradient', {'id': gradient.id}, refused=True)   # in use
    assert delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_gradient', {'id': other.id})['success']
    assert delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_design', {'id': design.id})['success']
    assert delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_gradient', {'id': gradient.id})['success']
    assert delete(superadmin_client, db_session, 'displayhive:admin:cts:delete_container', {'id': container.id})['success']


def test_deleting_a_user_and_a_group_with_everything_attached(db_session, superadmin_client, make_user, make_group, get_right):
    user = make_user()
    parent, child = make_group(), None
    child = make_group(parent=parent)
    right = get_right('media.page')
    db_session.add_all([UserGroup(user_id=user.id, group_id=child.id), UserRight(user_id=user.id, right_id=right.id, value='allow'),
                        GroupRight(group_id=child.id, right_id=right.id), AdminUserLogin(user_id=user.id, logged_in_at=now())])
    db_session.commit()
    delete(superadmin_client, db_session, 'displayhive:admin:rights:cts:delete_group', {'id': parent.id}, refused=True)      # has a subgroup
    delete(superadmin_client, db_session, 'displayhive:admin:users:cts:delete_user', {'id': user.id})
    delete(superadmin_client, db_session, 'displayhive:admin:rights:cts:delete_group', {'id': child.id})
    delete(superadmin_client, db_session, 'displayhive:admin:rights:cts:delete_group', {'id': parent.id})
    assert db_session.get(AdminUser, user.id) is None


def test_deleting_a_login_provider_keeps_the_identities_but_not_a_dangling_reference(db_session, superadmin_client, make_user):
    user = make_user()
    provider = AuthProvider(slug='dp-sso', name='SSO', issuer='https://sso.example', client_id='c')
    db_session.add(provider)
    db_session.flush()
    db_session.add(AdminUserIdentity(user_id=user.id, provider_id=provider.id, issuer='https://sso.example', subject='s1', created_at=now()))
    db_session.commit()
    delete(superadmin_client, db_session, 'displayhive:admin:authproviders:cts:delete_provider', {'id': provider.id})
    assert db_session.get(AuthProvider, provider.id) is None
