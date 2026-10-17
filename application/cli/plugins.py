"""`flask dh plugins …`: list, switch on and off, install and remove plugins from the command line.

The server picks changes up by itself only when it made them; after a command here, restart the service
(or use the Plugins page, which switches at run time).
"""

import click

from .group import dh


def _context():
    from flask import current_app
    from application.models import db
    return current_app, db


@dh.group('plugins')
def plugins_group():
    """Manage plugins."""


@plugins_group.command('list')
def plugins_list():
    """Show every plugin on disk and whether it is switched on."""
    from application.plugins import service
    app, db = _context()
    state = service.describe(db, app)
    for p in state['plugins']:
        flags = ('on ' if p['enabled'] else 'off') + (' bundled' if p['source'] == 'bundled' else ' installed')
        click.echo(f"{p['id']:<34} {p['version']:<9} {flags:<15} {p['name']}")


def _toggle(plugin_id: str, enabled: bool):
    from application.plugins import service
    from application.plugins.manifest import PluginError
    app, db = _context()
    try:
        service.set_enabled(db, app, plugin_id, enabled)
    except PluginError as problem:
        raise click.ClickException(str(problem))
    click.echo(f"{plugin_id}: {'switched on' if enabled else 'switched off'}. Restart a running server to apply it there.")


@plugins_group.command('enable')
@click.argument('plugin_id')
def plugins_enable(plugin_id):
    """Switch a plugin on."""
    _toggle(plugin_id, True)


@plugins_group.command('disable')
@click.argument('plugin_id')
def plugins_disable(plugin_id):
    """Switch a plugin off (its data is kept)."""
    _toggle(plugin_id, False)


@plugins_group.command('install')
@click.argument('source')
@click.option('--sha256', default='', help='Checksum of the file; required for a download link.')
def plugins_install(source, sha256):
    """Install a plugin from a ZIP file or a https:// link."""
    from application.plugins import service
    from application.plugins.manifest import PluginError
    app, db = _context()
    try:
        if source.startswith(('http://', 'https://')):
            manifest = service.install_url(db, app, source, sha256)
        else:
            with open(source, 'rb') as fh:
                manifest = service.install_zip(db, app, fh.read(), sha256=sha256)
    except (PluginError, OSError) as problem:
        raise click.ClickException(str(problem))
    click.echo(f'Installed {manifest.id} {manifest.version}.')


@plugins_group.command('remove')
@click.argument('plugin_id')
def plugins_remove(plugin_id):
    """Remove an installed plugin (its tables and data stay in the database)."""
    from application.plugins import service
    from application.plugins.manifest import PluginError
    app, db = _context()
    try:
        service.remove(db, app, plugin_id)
    except PluginError as problem:
        raise click.ClickException(str(problem))
    click.echo(f'Removed {plugin_id}.')
