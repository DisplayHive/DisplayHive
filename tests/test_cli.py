"""Tests for the `flask dh …` maintenance commands (application/cli.py) and
for how app.py recognises being loaded for one of them."""

import os
from datetime import datetime, timezone

import click
import pytest

from application.auth import verify_password, user_from_token, create_token


@pytest.fixture()
def cli(flask_app, db_session):
    runner = flask_app.app.test_cli_runner()

    def invoke(*args, input=None):
        return runner.invoke(args=['dh', *args], input=input)

    return invoke


def _user(db_session, username):
    from application.models import AdminUser
    return db_session.query(AdminUser).filter_by(username=username).one_or_none()


# --- create-admin / reset-password ------------------------------------------------


def test_create_admin_makes_a_superadmin(cli, flask_app, db_session):
    from application.permissions import is_superadmin

    result = cli('create-admin', 'cli-alice', '--password-stdin', input='a-long-password\n')
    assert result.exit_code == 0, result.output
    user = _user(db_session, 'cli-alice')
    assert verify_password('a-long-password', user.password_hash)
    assert user.password_login_allowed is True
    assert is_superadmin(flask_app.db, user)


def test_create_admin_options_and_errors(cli, flask_app, db_session, make_user):
    from application.permissions import is_superadmin

    result = cli('create-admin', 'cli-bob', '--password-stdin', '--no-superadmin', '--force-change',
                 input='a-long-password\n')
    assert result.exit_code == 0, result.output
    bob = _user(db_session, 'cli-bob')
    assert not is_superadmin(flask_app.db, bob)
    assert bob.must_change_password is True

    make_user(username='taken')
    result = cli('create-admin', 'taken', '--password-stdin', input='a-long-password\n')
    assert result.exit_code == 1 and 'already exists' in result.output

    result = cli('create-admin', 'cli-carol', '--password-stdin', input='short\n')
    assert result.exit_code == 1 and 'at least 8 characters' in result.output
    assert _user(db_session, 'cli-carol') is None


def test_create_admin_prompts_with_confirmation(cli, db_session):
    result = cli('create-admin', 'cli-dave', input='a-long-password\na-long-password\n')
    assert result.exit_code == 0, result.output
    assert verify_password('a-long-password', _user(db_session, 'cli-dave').password_hash)


def test_reset_password_restores_password_login_and_revokes_sessions(cli, flask_app, db_session, make_user):
    user = make_user(username='locked-out', is_active=False)
    user.password_login_allowed = False
    db_session.commit()
    old_token = create_token(flask_app.app, user)

    result = cli('reset-password', 'locked-out', '--password-stdin', '--activate', '--force-change',
                 input='brand-new-password\n')
    assert result.exit_code == 0, result.output
    db_session.refresh(user)
    assert verify_password('brand-new-password', user.password_hash)
    assert user.password_login_allowed is True
    assert user.is_active is True
    assert user.must_change_password is True
    assert user_from_token(flask_app.app, flask_app.db, old_token) is None


def test_reset_password_unknown_user_and_inactive_note(cli, make_user):
    assert cli('reset-password', 'nobody', '--password-stdin', input='x' * 10 + '\n').exit_code == 1
    make_user(username='sleeping', is_active=False)
    result = cli('reset-password', 'sleeping', '--password-stdin', input='x' * 10 + '\n')
    assert result.exit_code == 0 and '--activate' in result.output


# --- rerender (media) ----------------------------------------------------------


@pytest.fixture()
def big_image(flask_app, db_session):
    """A 2400×1200 PNG in DATA_DIR/media with its Media row (large enough for an FHD rendition)."""
    from PIL import Image
    from application.models import Media

    media_dir = flask_app.app.config['MEDIA_FOLDER']
    path = os.path.join(media_dir, 'cli-test.png')
    Image.new('RGB', (2400, 1200), (200, 30, 30)).save(path)
    db_session.add(Media(filename='cli-test.png', title='cli test', mime_type='image/png', file_size=1,
                         created_at=datetime.now(timezone.utc)))
    db_session.commit()
    yield 'cli-test.png'
    os.remove(path)


def test_rerender_creates_previews_and_renditions(cli, flask_app, big_image):
    from application import media_renditions

    config = flask_app.app.config
    preview = media_renditions.preview_path(config['PREVIEW_FOLDER'], big_image)
    fhd = media_renditions.rendition_path(config['MEDIA_RENDITIONS_FOLDER'], 'fhd', big_image)
    for path in (preview, fhd):
        if os.path.exists(path):
            os.remove(path)

    result = cli('rerender')
    assert result.exit_code == 0, result.output
    assert os.path.exists(preview) and os.path.exists(fhd)
    assert '1 preview(s)' in result.output

    # --missing-only leaves existing files alone; the default renders them again.
    os.utime(preview, (1, 1))
    os.utime(fhd, (1, 1))
    cli('rerender', '--missing-only')
    assert os.path.getmtime(preview) == 1
    cli('rerender')
    assert os.path.getmtime(preview) > 1 and os.path.getmtime(fhd) > 1


def test_rerender_reports_missing_originals(cli, db_session):
    from application.models import Media
    db_session.add(Media(filename='gone.png', title='gone', mime_type='image/png', file_size=1,
                         created_at=datetime.now(timezone.utc)))
    db_session.commit()
    result = cli('rerender')
    assert result.exit_code == 0
    assert 'missing on disk' in result.output


def test_rerender_content_runs(cli):
    result = cli('rerender-content')
    assert result.exit_code == 0 and 'Re-rendered' in result.output


# --- check-config --------------------------------------------------------------


def test_check_config_passes_on_the_test_instance(cli):
    result = cli('check-config')
    assert 'Schema is up to date' in result.output or 'has no schema revision' in result.output
    assert '[ OK ] SECRET_KEY is set' in result.output


def test_check_config_fails_without_a_password_superadmin(cli, db_session):
    from application.models import AdminUser
    for user in db_session.query(AdminUser).all():
        user.password_login_allowed = False
    db_session.commit()
    result = cli('check-config')
    assert result.exit_code == 1
    assert 'No active Superadmin with password login' in result.output or 'schema' in result.output


# --- CLI detection in app.py -----------------------------------------------------


@pytest.mark.parametrize('argv, expected', [
    (['flask', '--app', 'app', 'dh', 'check-config'], True),
    (['flask', '-A', 'app', 'dh', 'create-admin', 'run'], True),  # a user called "run"
    (['flask', '--app', 'app', 'run'], False),
    (['flask', '--debug', 'run', '--port', '5001'], False),
    (['flask', 'shell'], True),
])
def test_cli_detection(flask_app, monkeypatch, argv, expected):
    monkeypatch.setattr('sys.argv', argv)
    with click.Context(click.Command('flask')):
        assert flask_app._loaded_for_flask_cli_command() is expected


def test_no_cli_detection_outside_click(flask_app, monkeypatch):
    monkeypatch.setattr('sys.argv', ['gunicorn', 'app:app'])
    assert flask_app._loaded_for_flask_cli_command() is False
