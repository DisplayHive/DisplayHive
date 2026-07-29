"""Helpers for admin Designs page (server-side).

Provides helper to emit the designs list payload to admin clients.
"""

import logging
from typing import Optional

from application.models import Design

logger = logging.getLogger(__name__)


def emit_designs_update(socketio, app, db, room: Optional[str] = None):
    """Build a minimal designs payload and emit to clients.

    Payload shape: {'data': [ {id, name, description, isDefault}, ... ]}
    """
    try:
        all_designs = db.session.execute(db.select(Design)).scalars().all()
        designs = [
            {
                'id': d.id,
                'name': d.name,
                'description': d.description or '',
                'isDefault': bool(getattr(d, 'isDefault', False)),
            }
            for d in all_designs
        ]

        payload = {'data': designs}
        socketio.emit('displayhive:admin:stc:upd_designs', payload, room=room or 'admins')
    except Exception:
        logger.exception("Error emitting designs update")


def render_container_style_css(db, design_id: int) -> str:
    """Assemble `.dh-container-<id> { ... }` rules from this Design's stored
    per-container style overrides (DesignContainerStyle).

    Properties with a blank/whitespace-only value are skipped entirely
    (not rendered as `prop: ;`) — that's how a property is "unset" here.
    Returns '' if the Design has no overrides at all.
    """
    from application.models import DesignContainerStyle

    rows = db.session.execute(
        db.select(DesignContainerStyle)
        .where(DesignContainerStyle.design_id == design_id)
        .order_by(DesignContainerStyle.contentcontainer_id, DesignContainerStyle.id)
    ).scalars().all()

    by_container: dict = {}
    for row in rows:
        value = (row.value or '').strip()
        if not value:
            continue
        by_container.setdefault(row.contentcontainer_id, []).append((row.property, value))

    if not by_container:
        return ''

    blocks = []
    for container_id, props in by_container.items():
        decls = '\n'.join(f'  {prop}: {value};' for prop, value in props)
        blocks.append(f'.dh-container-{container_id} {{\n{decls}\n}}')
    return '\n\n'.join(blocks)


def render_global_style_css(db, design_id: int) -> str:
    """Assemble a single `.dh-container { ... }` rule from this Design's
    stored global style overrides (DesignGlobalStyle) — every container div
    carries this shared class, so it applies everywhere at once.

    Same blank-value-means-unset behavior as render_container_style_css().
    Returns '' if the Design has no global overrides at all.
    """
    from application.models import DesignGlobalStyle

    rows = db.session.execute(
        db.select(DesignGlobalStyle)
        .where(DesignGlobalStyle.design_id == design_id)
        .order_by(DesignGlobalStyle.id)
    ).scalars().all()

    props = [(row.property, (row.value or '').strip()) for row in rows if (row.value or '').strip()]
    if not props:
        return ''

    decls = '\n'.join(f'  {prop}: {value};' for prop, value in props)
    return f'.dh-container {{\n{decls}\n}}'
