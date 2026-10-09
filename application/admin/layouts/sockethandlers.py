import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_layouts_handlers(socketio, app, db):
    """Register socket handlers for the admin Layouts page.

    A Layout is a named, reusable group of ContentContainers (standalone
    entities with an explicit vh/vw position+size). Layout is purely an
    admin-side organizational concept — it scopes which containers a
    Contenttype's handlers may target; it has no runtime "screen uses this
    Layout" meaning.
    """
    from application.admin.layouts.helper import emit_layouts_update, emit_containers_update
    from application.socketio_handlers.actions import admin_action, Fail, ok
    from application.aspect_ratio import BASE_RATIO, normalize_ratio, parse_ratio_list, same_ratio
    from application.admin.layouts.helper import all_member_container_ids, container_geometry, containers_for_ratio
    from application.models import Layout, LayoutVariation, ContainerPosition, ContentContainer, Contenttype, TagConfig
    from application.utils import push_content_list_to_all_screens

    def _prune_stale_tagconfigs(layout):
        """Null out TagConfig.contentcontainer_id for any field whose target
        container is no longer part of *layout* — mirrors the same guard
        `_apply_tagconfigs` (contenttypes/sockethandlers.py) applies when a
        Contenttype's fields are saved directly. Without this, removing a
        container from a Layout here left every bound Contenttype's stale
        TagConfig pointing at it, and upd_content.py would keep rendering
        that container's old content even though it's no longer in the
        Layout — the field is kept, just unlinked from that container.
        """
        # A container is still "in" the Layout if any aspect-ratio variant has it.
        allowed_ids = all_member_container_ids(layout)
        contenttype_ids = db.session.execute(
            db.select(Contenttype.id).where(Contenttype.layout_id == layout.id)
        ).scalars().all()
        if not contenttype_ids:
            return
        stale = db.session.execute(
            db.select(TagConfig).where(
                TagConfig.contenttype_id.in_(contenttype_ids),
                TagConfig.contentcontainer_id.is_not(None),
                TagConfig.contentcontainer_id.not_in(allowed_ids),
            )
        ).scalars().all()
        for tc in stale:
            tc.contentcontainer_id = None
            db.session.add(tc)

    def _emit_layouts(room=None):
        emit_layouts_update(socketio, app, db, room=room)

    def _emit_containers(room=None):
        emit_containers_update(socketio, app, db, room=room)

    def _push_screens():
        # Container position/size/default-content and Layout membership can
        # change what's currently rendered on a screen — push a fresh
        # upd_content snapshot to everyone rather than waiting for their next
        # unrelated update or reconnect.
        try:
            push_content_list_to_all_screens(socketio, app, db)
        except Exception:
            logger.exception('Failed to push content update to screens')

    def _design_ratios():
        """Ratios the active Design offers (base first)."""
        from application.utils.design import get_default_design
        design = get_default_design(db)
        return [BASE_RATIO] + parse_ratio_list(getattr(design, 'aspect_ratios', None))

    def _ensure_position(container, ratio):
        """Give *container* its own position row at *ratio*, copied from its
        base columns, unless it already has one (positions are per container
        and ratio, shared by every Layout using the container)."""
        if any(p.aspect_ratio == ratio for p in container.positions):
            return
        g = container_geometry(container, BASE_RATIO)
        db.session.add(ContainerPosition(contentcontainer_id=container.id, aspect_ratio=ratio, **g))
        db.session.flush()
        db.session.refresh(container)

    def _find_variation(layout, ratio):
        return next((v for v in layout.variations if v.aspect_ratio == ratio), None)

    @socketio.on('displayhive:admin:cts:get_aspect_ratios')
    @admin_action('layouts.page', 'screens.page', 'content.page', 'designs.page')
    def get_aspect_ratios(message=None):
        socketio.emit('displayhive:admin:stc:aspect_ratios', {'ratios': _design_ratios()}, room=request.sid)

    @socketio.on('displayhive:admin:cts:create_layout_variation')
    @admin_action('layouts.edit')
    def handle_create_layout_variation(data=None):
        """Add a variation of a Layout at *aspect_ratio* (must be one of the
        active Design's ratios). Starts as a copy of the base membership and
        positions. Payload: {layout_id, aspect_ratio}."""
        data = data if isinstance(data, dict) else {}
        layout = db.session.get(Layout, int(data.get('layout_id') or 0))
        if not layout:
            raise Fail('Layout not found')
        ratio = normalize_ratio(data.get('aspect_ratio'))
        if not ratio or ratio == BASE_RATIO:
            raise Fail('Invalid aspect ratio')
        if ratio not in _design_ratios():
            raise Fail('Aspect ratio is not defined in the active Design')
        if any(same_ratio(ratio, v.aspect_ratio) for v in layout.variations):
            raise Fail('This variation already exists')
        variation = LayoutVariation(layout_id=layout.id, aspect_ratio=ratio)
        variation.contentcontainers = list(layout.contentcontainers)
        db.session.add(variation)
        for c in layout.contentcontainers:
            _ensure_position(c, ratio)
        db.session.commit()
        _emit_layouts()
        _emit_containers()
        _push_screens()
        return {'success': True}

    @socketio.on('displayhive:admin:cts:delete_layout_variation')
    @admin_action('layouts.edit')
    def handle_delete_layout_variation(data=None):
        """Remove a Layout's variation. Payload: {layout_id, aspect_ratio}.
        Container positions at that ratio are kept (they belong to the
        containers, which other Layouts may still use)."""
        data = data if isinstance(data, dict) else {}
        layout = db.session.get(Layout, int(data.get('layout_id') or 0))
        if not layout:
            raise Fail('Layout not found')
        variation = _find_variation(layout, normalize_ratio(data.get('aspect_ratio')) or '')
        if not variation:
            raise Fail('Variation not found')
        db.session.delete(variation)
        db.session.flush()
        db.session.refresh(layout)
        _prune_stale_tagconfigs(layout)
        db.session.commit()
        _emit_layouts()
        _push_screens()
        return {'success': True}

    def _resolve_container_ids(container_ids):
        ids = list(dict.fromkeys(
            int(cid) for cid in (container_ids or [])
            if str(cid).isdigit() or isinstance(cid, int)
        ))
        if not ids:
            return []
        return db.session.execute(
            db.select(ContentContainer).where(ContentContainer.id.in_(ids))
        ).scalars().all()

    # --- Layouts ---------------------------------------------------------

    @socketio.on('displayhive:admin:cts:get_layouts')
    @admin_action('layouts.page')
    def get_admin_layouts(message=None):
        _emit_layouts(room=request.sid)

    @socketio.on('displayhive:admin:cts:get_design_preview')
    @admin_action('layouts.page')
    def get_design_preview(message=None):
        """Emit the active Design's {name, html, css} — same shape/CSS
        layering `upd_content` pushes to real screens — so the Layout editor
        can render it behind the container-positioning canvas. Read-only:
        gated by `layouts.page` (not a Designs right), same as get_containers
        above, since this is just a backdrop for placing containers, not
        Design editing.
        """
        from application.admin.designs.helper import build_design_payload
        payload = build_design_payload(db)
        socketio.emit('displayhive:admin:stc:design_preview', payload, room=request.sid)

    # --- Container design (active Design's per-container styles) ----------
    # Surfaced as the Layout editor's "Container Design". Operates on the *active*
    # Design only (the one the canvas previews), gated by designs.edit OR the
    # narrower contenttypes.edit_design, so a Layout editor can restyle a
    # container without being granted the whole Designs page.

    @socketio.on('displayhive:admin:cts:get_container_design')
    @admin_action('designs.edit', 'contenttypes.edit_design')
    def get_container_design(message=None):
        """Emit the active Design's id and per-container style overrides.

        Payload: {design_id, data: {contentcontainer_id: {property: value}}}
        (design_id is null if no Design is active).
        """
        from application.models import DesignContainerStyle
        from application.utils.design import get_default_design
        design = get_default_design(db)
        by_container: dict = {}
        if design is not None:
            rows = db.session.execute(
                db.select(DesignContainerStyle).where(DesignContainerStyle.design_id == design.id)
            ).scalars().all()
            for row in rows:
                by_container.setdefault(str(row.contentcontainer_id), {})[row.property] = row.value or ''
        socketio.emit('displayhive:admin:stc:container_design', {
            'design_id': design.id if design is not None else None,
            'data': by_container,
        }, room=request.sid)

    @socketio.on('displayhive:admin:cts:save_container_design')
    @admin_action('designs.edit', 'contenttypes.edit_design')
    def save_container_design(data=None):
        """Upsert one container's style overrides on the active Design.

        Payload: {contentcontainer_id, styles: {property: value}}. Refreshes
        the caller's design preview and reloads screens (the active Design is
        what screens show).
        """
        from application.admin.designs.helper import build_design_payload, upsert_container_styles
        from application.utils.design import get_default_design
        if not data or not isinstance(data, dict):
            raise Fail('Invalid payload')
        contentcontainer_id = data.get('contentcontainer_id')
        styles = data.get('styles')
        if not contentcontainer_id or not isinstance(styles, dict):
            raise Fail('Missing contentcontainer_id or styles')
        design = get_default_design(db)
        if design is None:
            raise Fail('No active design')
        if db.session.get(ContentContainer, int(contentcontainer_id)) is None:
            raise Fail('Container not found')

        upsert_container_styles(db, design.id, int(contentcontainer_id), styles)
        db.session.commit()
        try:
            from application.utils import reload_devices_on_all_screens
            reload_devices_on_all_screens(socketio, db)
        except Exception:
            logger.exception('Failed to reload screens after container design change')
        socketio.emit('displayhive:admin:stc:design_preview', build_design_payload(db), room=request.sid)
        return {'success': True}

    @socketio.on('displayhive:admin:cts:get_layout_default_content_preview')
    @admin_action('layouts.page')
    def get_layout_default_content_preview(message=None):
        """Emit each of a Layout's containers' own fallback content, rendered
        through its default_field_handler and positioned per the Layout — same
        {top, left, width, height, html} shape build_scene_containers hands the
        Content list/edit previews, so the Layout editor's canvas can show
        "what a screen falls back to here" without a Contenttype/ContentElement
        in the picture at all. Read-only, gated like get_design_preview above.
        """
        layout_id = (message or {}).get('layout_id')
        if not layout_id:
            return
        layout = db.session.get(Layout, int(layout_id))
        if not layout:
            return

        from application.admin.content.helper import combine_layout_containers
        ratio = normalize_ratio((message or {}).get('aspect_ratio')) or BASE_RATIO
        containers = combine_layout_containers(containers_for_ratio(layout, ratio), {}, db=db, ratio=ratio)
        socketio.emit('displayhive:admin:stc:layout_default_content_preview', {
            'layout_id': layout.id,
            'aspect_ratio': ratio,
            'containers': containers,
        }, room=request.sid)

    _SNAPLINES_SETTING_KEY = 'layout_snaplines'

    def _load_snaplines():
        """Return the globally-shared canvas snaplines as a list of
        {axis: 'h'|'v', position: float} dicts, stored as one JSON blob in
        SystemSetting (same generic key/value store the Settings page uses)
        rather than scoped to a single Layout — these are alignment guides
        meant to be reused across every Layout's canvas.
        """
        import json
        from application.models import SystemSetting
        row = db.session.execute(
            db.select(SystemSetting).where(SystemSetting.key == _SNAPLINES_SETTING_KEY)
        ).scalar_one_or_none()
        if not row or not row.value:
            return []
        try:
            data = json.loads(row.value)
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def _emit_snaplines(room=None):
        socketio.emit(
            'displayhive:admin:stc:layout_snaplines',
            {'snaplines': _load_snaplines()},
            room=room,
        )

    @socketio.on('displayhive:admin:cts:get_layout_snaplines')
    @admin_action('layouts.page')
    def get_layout_snaplines(message=None):
        _emit_snaplines(room=request.sid)

    @socketio.on('displayhive:admin:cts:set_layout_snaplines')
    @admin_action('layouts.edit')
    def handle_set_layout_snaplines(data=None):
        """Replace the whole global snaplines list. data = {snaplines: [{axis, position}, ...]}"""
        import json
        from application.models import SystemSetting

        raw = (data or {}).get('snaplines')
        if not isinstance(raw, list):
            raise Fail('snaplines must be a list')

        cleaned = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            axis = item.get('axis')
            if axis not in ('h', 'v'):
                continue
            try:
                position = float(item.get('position'))
            except (TypeError, ValueError):
                continue
            if not (0 <= position <= 100):
                continue
            cleaned.append({'axis': axis, 'position': position})

        row = db.session.execute(
            db.select(SystemSetting).where(SystemSetting.key == _SNAPLINES_SETTING_KEY)
        ).scalar_one_or_none()
        value = json.dumps(cleaned)
        if row:
            row.value = value
        else:
            db.session.add(SystemSetting(key=_SNAPLINES_SETTING_KEY, value=value))
        db.session.commit()

        _emit_snaplines(room='admins')
        return {'success': True}

    @socketio.on('displayhive:admin:cts:create_layout')
    @admin_action('layouts.create')
    def handle_create_layout(data=None):
        if not data or not isinstance(data, dict):
            raise Fail('Invalid payload')
        layout = Layout(name=data.get('name', ''), description=data.get('description', ''))
        db.session.add(layout)
        db.session.flush()
        layout.contentcontainers = _resolve_container_ids(data.get('container_ids'))
        # Optional copy of aspect-ratio variations: [{aspect_ratio, container_ids}]
        allowed_ratios = _design_ratios()
        for item in (data.get('variations') or []):
            if not isinstance(item, dict):
                continue
            ratio = normalize_ratio(item.get('aspect_ratio'))
            if not ratio or ratio == BASE_RATIO or ratio not in allowed_ratios:
                continue
            if any(same_ratio(ratio, v.aspect_ratio) for v in layout.variations):
                continue
            variation = LayoutVariation(layout_id=layout.id, aspect_ratio=ratio)
            variation.contentcontainers = _resolve_container_ids(item.get('container_ids'))
            db.session.add(variation)
            db.session.flush()
            for c in variation.contentcontainers:
                _ensure_position(c, ratio)
        db.session.commit()
        _emit_layouts()
        _push_screens()
        return {'success': True, 'id': layout.id}

    @socketio.on('displayhive:admin:cts:update_layout')
    @admin_action('layouts.edit')
    def handle_update_layout(data=None):
        if not data or not isinstance(data, dict):
            raise Fail('Invalid payload')
        layout_id = data.get('id')
        if not layout_id:
            raise Fail('Missing id')
        layout = db.session.get(Layout, int(layout_id))
        if not layout:
            raise Fail('Layout not found')

        layout.name = data.get('name', layout.name)
        layout.description = data.get('description', layout.description)
        container_ids = data.get('container_ids')
        if container_ids is not None:
            # Membership of one aspect-ratio variant: the base (default) or,
            # with `aspect_ratio`, that variation's own container set.
            ratio = normalize_ratio(data.get('aspect_ratio')) or BASE_RATIO
            containers = _resolve_container_ids(container_ids)
            if ratio == BASE_RATIO:
                layout.contentcontainers = containers
            else:
                variation = _find_variation(layout, ratio)
                if not variation:
                    raise Fail('Variation not found')
                variation.contentcontainers = containers
                for c in containers:
                    _ensure_position(c, ratio)
            db.session.flush()
            db.session.refresh(layout)
            _prune_stale_tagconfigs(layout)

        db.session.add(layout)
        db.session.commit()
        _emit_layouts()
        _push_screens()
        return {'success': True}

    @socketio.on('displayhive:admin:cts:delete_layout')
    @admin_action('layouts.delete')
    def handle_delete_layout(data=None):
        if not data or not isinstance(data, dict):
            raise Fail('Invalid payload')
        layout_id = data.get('id')
        if not layout_id:
            raise Fail('Missing id')
        layout = db.session.get(Layout, int(layout_id))
        if not layout:
            raise Fail('Layout not found')
        if layout.contenttypes:
            raise Fail(f'Layout is used by {len(layout.contenttypes)} content type(s)')
        db.session.delete(layout)
        db.session.commit()
        _emit_layouts()
        _push_screens()
        return {'success': True}

    # --- Content Containers (standalone entities) -------------------------

    @socketio.on('displayhive:admin:cts:get_containers')
    @admin_action('layouts.page')
    def get_admin_containers(message=None):
        _emit_containers(room=request.sid)

    @socketio.on('displayhive:admin:cts:create_container')
    @admin_action('layouts.create')
    def handle_create_container(data=None):
        if not data or not isinstance(data, dict):
            raise Fail('Invalid payload')
        container = ContentContainer(
            name=data.get('name', ''),
            order=int(data.get('order') or 0),
            top=float(data.get('top') or 0),
            left=float(data.get('left') or 0),
            width=float(data.get('width') or 100),
            height=float(data.get('height') or 100),
            default_field_handler=data.get('default_field_handler') or None,
            default_content=data.get('default_content') or None,
            show_when_empty=bool(data.get('show_when_empty')),
        )
        db.session.add(container)
        db.session.commit()
        _emit_containers()
        _push_screens()
        return {'success': True, 'id': container.id}

    @socketio.on('displayhive:admin:cts:update_container')
    @admin_action('layouts.edit')
    def handle_update_container(data=None):
        if not data or not isinstance(data, dict):
            raise Fail('Invalid payload')
        container_id = data.get('id')
        if not container_id:
            raise Fail('Missing id')
        container = db.session.get(ContentContainer, int(container_id))
        if not container:
            raise Fail('Container not found')

        # Apply 'locked' first so a request that unlocks and repositions in
        # the same call (e.g. the editor's own toggle-then-drag) is allowed,
        # while a stray position update against an otherwise-locked
        # container is rejected below rather than silently applied.
        if 'locked' in data:
            container.locked = bool(data.get('locked'))

        position_fields = ('top', 'left', 'width', 'height')
        if container.locked and any(data.get(f) is not None for f in position_fields):
            raise Fail('Container is locked')

        container.name = data.get('name', container.name)
        for field in ('order',):
            if data.get(field) is not None:
                setattr(container, field, int(data[field]))
        # Position/size belong to one aspect ratio: the base (columns on the
        # container) or, with `aspect_ratio`, that ratio's own ContainerPosition.
        # Every other property above/below is shared across ratios.
        ratio = normalize_ratio(data.get('aspect_ratio')) or BASE_RATIO
        if ratio == BASE_RATIO:
            for field in position_fields:
                if data.get(field) is not None:
                    setattr(container, field, float(data[field]))
        elif any(data.get(f) is not None for f in position_fields):
            _ensure_position(container, ratio)
            pos = next(p for p in container.positions if p.aspect_ratio == ratio)
            for field in position_fields:
                if data.get(field) is not None:
                    setattr(pos, field, float(data[field]))
            db.session.add(pos)
        # Explicit keys (rather than "is not None") so clearing either field
        # back to "no default" by sending an empty value actually takes effect.
        if 'default_field_handler' in data:
            container.default_field_handler = data.get('default_field_handler') or None
        if 'default_content' in data:
            container.default_content = data.get('default_content') or None
        if 'show_when_empty' in data:
            container.show_when_empty = bool(data.get('show_when_empty'))

        db.session.add(container)
        db.session.commit()
        _emit_containers()
        _push_screens()
        return {'success': True}

    @socketio.on('displayhive:admin:cts:delete_container')
    @admin_action('layouts.delete')
    def handle_delete_container(data=None):
        from application.models import TagConfig, DesignContainerStyle
        from application.models.content import layout_variation_container

        if not data or not isinstance(data, dict):
            raise Fail('Invalid payload')
        container_id = data.get('id')
        if not container_id:
            raise Fail('Missing id')
        container = db.session.get(ContentContainer, int(container_id))
        if not container:
            raise Fail('Container not found')
        used_by = db.session.execute(
            db.select(db.func.count()).select_from(TagConfig).where(TagConfig.contentcontainer_id == container.id)
        ).scalar_one()
        if used_by:
            raise Fail(f'Container is used by {used_by} field(s)')
        db.session.execute(
            db.delete(DesignContainerStyle).where(DesignContainerStyle.contentcontainer_id == container.id)
        )
        # Variation membership rows aren't covered by a relationship back to
        # the container, and SQLite doesn't enforce the FK cascade here.
        db.session.execute(
            db.delete(layout_variation_container).where(layout_variation_container.c.contentcontainer_id == container.id)
        )
        db.session.delete(container)
        db.session.commit()
        _emit_containers()
        _push_screens()
        return {'success': True}
