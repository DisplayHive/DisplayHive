"""The plugin's rights got the plugin's id as prefix: pretalx.page → displayhive.pretalx.page.

Groups and users hold a right through the right's row, not its name, so renaming the row keeps every
assignment as it was.
"""

import sqlalchemy as sa


def upgrade(connection):
    for old, new in (('pretalx.page', 'displayhive.pretalx.page'), ('pretalx.manage', 'displayhive.pretalx.manage')):
        if connection.execute(sa.text('SELECT 1 FROM right_definition WHERE key = :key'), {'key': new}).first():
            continue
        connection.execute(sa.text('UPDATE right_definition SET key = :new WHERE key = :old'), {'new': new, 'old': old})
