import json
import logging

from flask import request

logger = logging.getLogger(__name__)


def register_admin_templates_handlers(socketio, app, db):
    """Register socket handlers for the admin Templates page."""
    from application.admin.templates.helper import emit_templates_update
    from application.socketio_handlers.auth import require_right
    from application.models import Template, ContentContainer

    def _emit_templates(room=None):
        """Broadcast the current templates list."""
        emit_templates_update(socketio, app, db, room=room)

    @socketio.on('displayhive:admin:cts:get_templates')
    @require_right('templates.page')
    def get_admin_templates(message=None):
        """Emit the current templates list to the requesting client."""
        _emit_templates(room=request.sid)

    @socketio.on('displayhive:admin:cts:get_template')
    @require_right('templates.page')
    def get_template(message=None):
        """Emit full template detail (including html and css) for a single template id."""
        if not message or not isinstance(message, dict):
            return
        tpl_id = message.get('id') or message.get('template_id')
        if not tpl_id:
            return
        tpl = db.session.get(Template, int(tpl_id))
        if not tpl:
            return
        containers = getattr(tpl, 'contentcontainers', []) or []
        payload = {
            'template': {
                'id': tpl.id,
                'name': tpl.name,
                'description': tpl.description or '',
                'html': tpl.html or '',
                'css': tpl.css or '',
                'is_default': bool(getattr(tpl, 'isDefault', False)),
                'container_count': len(containers),
                'containers': [
                    {'id': c.id, 'name': c.name, 'order': c.order, 'title': c.title or ''}
                    for c in containers
                ],
            }
        }
        socketio.emit('displayhive:admin:stc:template_detail', payload, room=request.sid)

    @socketio.on('displayhive:admin:cts:create_template')
    @require_right('templates.create')
    def handle_create_template(data=None):
        """Create a template from socket payload. Accepts container_config to create ContentContainer rows."""
        if not data or not isinstance(data, dict):
            return

        template = Template(
            name=data.get('name', ''),
            description=data.get('description', ''),
            html=data.get('html', ''),
            css=data.get('css', ''),
        )
        db.session.add(template)
        db.session.flush()

        container_config = data.get('container_config') or ''
        if container_config:
            try:
                cfg = container_config if isinstance(container_config, dict) else json.loads(container_config)
                for tag_name, tag_data in (cfg.items() if isinstance(cfg, dict) else []):
                    db.session.add(ContentContainer(
                        name=tag_name, template_id=template.id,
                        order=tag_data.get('order', 0), title=tag_data.get('title', ''),
                    ))
            except Exception:
                logger.exception('create_template: failed to parse container_config')

        db.session.commit()
        _emit_templates()

    @socketio.on('displayhive:admin:cts:update_template')
    @require_right('templates.edit')
    def handle_update_template(data=None):
        """Update a template and its containers from socket payload."""
        if not data or not isinstance(data, dict):
            return
        tpl_id = data.get('id')
        if not tpl_id:
            return

        tpl = db.session.get(Template, int(tpl_id))
        if not tpl:
            return

        tpl.name = data.get('name', tpl.name)
        tpl.description = data.get('description', tpl.description)
        tpl.html = data.get('html', tpl.html)
        tpl.css = data.get('css', tpl.css)

        container_config = data.get('container_config')
        if container_config is not None:
            try:
                cfg = container_config if isinstance(container_config, dict) else json.loads(container_config)
                existing_containers = db.session.execute(
                    db.select(ContentContainer).where(ContentContainer.template_id == tpl.id)
                ).scalars().all()
                existing_map = {c.name: c for c in existing_containers}

                for tag_name, tag_data in (cfg.items() if isinstance(cfg, dict) else []):
                    if tag_name in existing_map:
                        c = existing_map[tag_name]
                        c.order = tag_data.get('order', c.order)
                        c.title = tag_data.get('title', c.title)
                    else:
                        db.session.add(ContentContainer(
                            name=tag_name, template_id=tpl.id,
                            order=tag_data.get('order', 0), title=tag_data.get('title', ''),
                        ))

                cfg_names = set(cfg.keys()) if isinstance(cfg, dict) else set()
                for c in existing_containers:
                    if c.name not in cfg_names:
                        db.session.delete(c)
            except Exception:
                logger.exception('update_template: failed to apply container_config')

        db.session.add(tpl)
        db.session.commit()
        _emit_templates()

        try:
            from application.utils import reload_devices_for_template
            reload_devices_for_template(socketio, db, tpl)
        except Exception:
            logger.exception('update_template: failed to reload screens using this template')

    @socketio.on('displayhive:admin:cts:delete_template')
    @require_right('templates.delete')
    def handle_delete_template(data=None):
        """Delete a template by id (socket)."""
        if not data or not isinstance(data, dict):
            return
        tpl_id = data.get('id') or data.get('template_id')
        if not tpl_id:
            return

        tpl = db.session.get(Template, int(tpl_id))
        if not tpl:
            return

        for c in db.session.execute(
            db.select(ContentContainer).where(ContentContainer.template_id == tpl.id)
        ).scalars().all():
            db.session.delete(c)

        db.session.delete(tpl)
        db.session.commit()
        _emit_templates()
