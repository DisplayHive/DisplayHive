"""Rich text (WYSIWYG): the stored value is used as it is (no transformation on the server)."""

from application.plugins.handlers import FieldHandler


class Handler(FieldHandler):
    id = 'wysiwyg'


def register(api):
    api.fieldhandlers.add(Handler())
