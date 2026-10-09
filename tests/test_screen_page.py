"""The screen page (frontends/screen/templates/index.html) as the browser parses it."""

import re


def test_the_design_css_script_is_one_complete_script(flask_app):
    """A closing script tag inside the inline script (even in a comment) ends it early and the rest
    of the script is shown as text on every screen."""
    html = flask_app.app.test_client().get('/').get_data(as_text=True)
    start = html.index('<script>')
    end = html.index('</script>', start)
    script = html[start:end]
    assert "getElementById('design-css')" in script
    assert 'console.warn' in script  # the end of the script, i.e. nothing cut it short


def test_design_css_with_script_end_tag_stays_inside_the_string(flask_app, db_session):
    from application.models import Design, db
    design = Design(name='evil', html='', css='</script><b id="x">hi</b>', isDefault=True)
    for d in db_session.execute(db.select(Design)).scalars():
        d.isDefault = False
    db_session.add(design)
    db_session.commit()
    html = flask_app.app.test_client().get('/').get_data(as_text=True)
    assert '<b id="x">' not in html
    assert re.search(r'\\u003c/script\\u003e|<\\/script>', html)
