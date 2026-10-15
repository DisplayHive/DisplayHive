"""What the admin's HTTP endpoints (export, import, demo, REST) answer when they crash.

Flask's own answer to an unexpected exception is an HTML page, which the admin cannot show.
For the JSON endpoints it becomes the same ``{'success': False, 'error': …, 'error_ref': …}``
the socket handlers give (see ``socketio_handlers/actions.py``), with a short reference that
is also written to the log. Flask has logged the traceback itself just before.
"""

import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import InternalServerError

logger = logging.getLogger(__name__)

# The paths the admin frontend calls with fetch(); everything else keeps Flask's default page.
JSON_PREFIXES = ('/admin/api/', '/admin/export/', '/admin/import/', '/admin/demo/')


def internal_error_response(error):
    """The JSON answer for a 500 on one of ``JSON_PREFIXES``; ``error`` unchanged otherwise."""
    if not request.path.startswith(JSON_PREFIXES):
        return error
    from application.socketio_handlers.actions import internal_failure, new_error_reference
    reference = new_error_reference()
    logger.error('Unhandled error on %s %s (reference %s)', request.method, request.path, reference)
    return jsonify(internal_failure(reference)), 500


def register_error_handlers(app: Flask) -> None:
    app.register_error_handler(InternalServerError, internal_error_response)
