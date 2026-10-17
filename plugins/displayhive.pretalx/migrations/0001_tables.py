"""The plugin's tables, for databases that do not have them.

DisplayHive's own migrations created these tables back when the Pretalx page was part of the core, so on
every database that was ever migrated this does nothing. It is for databases that were built from the
models (a development SQLite file, the tests), where the tables were never created because they are no
longer part of the core.
"""

import sqlalchemy as sa


def upgrade(connection):
    existing = set(sa.inspect(connection).get_table_names())
    meta = sa.MetaData()
    sa.Table(
        'pretalx_api_url', meta,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('polling_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('polling_interval', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('last_success', sa.DateTime(), nullable=True),
        sa.Column('last_failure', sa.DateTime(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=True),
    )
    sa.Table(
        'pretalx_api_cache', meta,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('api_url_id', sa.Integer(), sa.ForeignKey('pretalx_api_url.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cached_json', sa.Text(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
    )
    sa.Table(
        'pretalx_settings', meta,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('time_format', sa.String(50), nullable=False, server_default='HH:mm'),
        sa.Column('end_of_day', sa.String(5), nullable=False, server_default='23:59'),
        sa.Column('no_session_text', sa.String(500), nullable=False, server_default='No session running'),
        sa.Column('coming_up_text', sa.String(500), nullable=False, server_default='Coming up next'),
        sa.Column('invalid_data_text', sa.String(500), nullable=False, server_default='Invalid API data'),
        sa.Column('sim_datetime', sa.String(20), nullable=True),
    )
    meta.create_all(connection, tables=[t for t in meta.sorted_tables if t.name not in existing])
