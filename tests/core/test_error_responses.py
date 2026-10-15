"""The JSON answer the admin's HTTP endpoints give when they crash (application/web/errors.py)."""

import json

from werkzeug.exceptions import InternalServerError


def test_a_crash_on_an_admin_json_endpoint_answers_json_with_a_reference(flask_app):
    from application.web.errors import internal_error_response

    with flask_app.app.test_request_context('/admin/export/download', method='POST'):
        response, status = internal_error_response(InternalServerError())
    body = json.loads(response.get_data(as_text=True))
    assert status == 500
    assert body['success'] is False
    assert body['error_ref'] and body['error_ref'] in body['error']
    assert 'server log' in body['error']


def test_other_paths_keep_the_default_answer(flask_app):
    from application.web.errors import internal_error_response

    error = InternalServerError()
    with flask_app.app.test_request_context('/healthz'):
        assert internal_error_response(error) is error


def test_the_handler_is_registered(flask_app):
    assert InternalServerError in flask_app.app.error_handler_spec[None][500]
