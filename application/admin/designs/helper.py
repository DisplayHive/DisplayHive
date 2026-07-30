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


def gradient_css_value(gradient) -> str:
    """Return this Gradient's CSS function value, covering the three
    widely-supported gradient functions and their `repeating-` variants:

      linear-gradient(<angle>deg, <stops>)
      radial-gradient(<shape> <size> at <x>% <y>%, <stops>)
      conic-gradient(from <angle>deg at <x>% <y>%, <stops>)

    `shape`/`size` are blank-safe (CSS just uses its own default — ellipse
    farthest-corner — when omitted). Each stop's `opacity` (0-100, defaults
    to 100/opaque) becomes an 8-digit hex alpha channel — without it, a
    gradient with no transparent stops always completely hides any gradient
    layers listed after it, since CSS stacks background-image layers with
    the first-listed one on top. Returns '' if the gradient has fewer than
    two stops (a gradient needs at least two) or an unknown type.
    """
    import json

    if not gradient or not gradient.stops:
        return ''
    try:
        stops = json.loads(gradient.stops)
    except Exception:
        return ''
    if not isinstance(stops, list) or len(stops) < 2:
        return ''

    def _stop_color(s):
        color = str(s.get('color', '#000000'))
        opacity = s.get('opacity', 100)
        try:
            opacity = float(opacity)
        except (TypeError, ValueError):
            opacity = 100
        if opacity >= 100 or not color.startswith('#') or len(color) != 7:
            return color
        alpha = round(max(0, min(100, opacity)) / 100 * 255)
        return f'{color}{alpha:02x}'

    stop_str = ', '.join(f"{_stop_color(s)} {s.get('position', 0)}%" for s in stops)
    prefix = 'repeating-' if gradient.repeating else ''
    gtype = gradient.type or 'linear'
    x = gradient.position_x if gradient.position_x is not None else 50
    y = gradient.position_y if gradient.position_y is not None else 50

    if gtype == 'linear':
        return f'{prefix}linear-gradient({int(gradient.angle or 0)}deg, {stop_str})'

    if gtype == 'radial':
        shape_size = ' '.join(p for p in (gradient.shape or '', gradient.size or '') if p)
        head = f'{shape_size} at {x}% {y}%'.strip()
        return f'{prefix}radial-gradient({head}, {stop_str})'

    if gtype == 'conic':
        return f'{prefix}conic-gradient(from {int(gradient.angle or 0)}deg at {x}% {y}%, {stop_str})'

    return ''


def render_gradient_css(db, design_id: int) -> str:
    """Assemble the `body { background-image: ...; }` rule from every
    Gradient applied to this Design, stacked as comma-separated layers in
    their configured order (lower DesignGradient.order = listed first, i.e.
    the frontmost layer). Returns '' if the Design has no gradients applied.
    """
    from application.models import DesignGradient, Gradient

    rows = db.session.execute(
        db.select(Gradient)
        .join(DesignGradient, DesignGradient.gradient_id == Gradient.id)
        .where(DesignGradient.design_id == design_id)
        .order_by(DesignGradient.order, DesignGradient.id)
    ).scalars().all()

    values = [v for v in (gradient_css_value(g) for g in rows) if v]
    if not values:
        return ''
    return 'body {\n  background-image: ' + ', '.join(values) + ';\n}'
