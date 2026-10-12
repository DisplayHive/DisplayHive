"""The `flask dh` command group every command module registers on."""

from flask.cli import AppGroup

dh = AppGroup('dh', help='DisplayHive maintenance commands.')
