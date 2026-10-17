"""The QR code field handler (plugins/displayhive.qrcode): what each kind of code says, and what is drawn."""

import importlib
import json
import sys

import pytest

from application.admin.content.helper import render_default_value
from application.plugins.handlers import RenderContext
from application.plugins.registry import registry


@pytest.fixture(scope='module')
def qr(flask_app):
    """The plugin's modules, as loaded by the server."""
    handler = registry.fieldhandler('qrcode')
    assert handler is not None, 'the QR code plugin is bundled and preinstalled'
    package = type(handler).__module__
    return {'init': sys.modules[package], 'payload': importlib.import_module(package + '.payload')}


def render(values, name='code'):
    return str(registry.fieldhandler('qrcode').render(RenderContext(field_name=name, values=values, db=None, tagconfig=None)))


# --- What the codes say -------------------------------------------------------------------------

def test_wifi_escapes_what_the_format_reserves(qr):
    assert qr['payload'].wifi({'wifi_ssid': 'Cafe;1', 'wifi_password': 'p:a"s,s', 'wifi_security': 'WPA'}) == r'WIFI:T:WPA;S:Cafe\;1;P:p\:a\"s\,s;;'
    assert qr['payload'].wifi({'wifi_ssid': 'Open', 'wifi_security': 'nopass', 'wifi_password': 'ignored', 'wifi_hidden': 'true'}) == 'WIFI:T:nopass;S:Open;H:true;;'
    assert qr['payload'].wifi({'wifi_password': 'x'}) == ''


def test_vcard_and_mecard(qr):
    values = {'vc_first': 'Ada', 'vc_last': 'Lovelace', 'vc_org': 'Analytical; Ltd', 'vc_phone': '+49 30 1234', 'vc_email': 'ada@example.org',
              'vc_street': 'Main St 1', 'vc_zip': '10115', 'vc_city': 'Berlin', 'vc_country': 'DE', 'vc_note': 'line1\nline2'}
    card = qr['payload'].vcard(values)
    assert card.startswith('BEGIN:VCARD\nVERSION:3.0\nN:Lovelace;Ada;;;\nFN:Ada Lovelace')
    assert 'ORG:Analytical\; Ltd' in card and 'NOTE:line1\\nline2' in card
    assert 'ADR;TYPE=WORK:;;Main St 1;Berlin;;10115;DE' in card and card.endswith('END:VCARD')
    mecard = qr['payload'].vcard({**values, 'vc_format': 'mecard'})
    assert mecard.startswith('MECARD:N:Lovelace,Ada;TEL:+49 30 1234;EMAIL:ada@example.org;') and mecard.endswith(';;')
    assert qr['payload'].vcard({}) == ''


def test_email_sms_phone_geo(qr):
    p = qr['payload']
    assert p.email({'mail_to': 'a@b.org', 'mail_subject': 'Hi there', 'mail_body': 'A&B'}) == 'mailto:a@b.org?subject=Hi%20there&body=A%26B'
    assert p.email({'mail_to': 'a@b.org'}) == 'mailto:a@b.org'
    assert p.sms({'sms_number': '+49 170 123', 'sms_message': 'Hello'}) == 'SMSTO:+49170123:Hello'
    assert p.phone({'tel_number': '(030) 123-45'}) == 'tel:03012345'
    assert p.geo({'geo_lat': '52,52', 'geo_lon': '13.405'}) == 'geo:52.52,13.405'
    assert p.geo({'geo_lat': '91', 'geo_lon': '0'}) == '' and p.geo({'geo_lat': 'x', 'geo_lon': '0'}) == ''


def test_event(qr):
    text = qr['payload'].event({'ev_title': 'DHCON', 'ev_start': '2027-03-17T09:00', 'ev_end': '2027-03-18T17:30', 'ev_location': 'Berlin'})
    assert text.split('\n') == ['BEGIN:VCALENDAR', 'VERSION:2.0', 'BEGIN:VEVENT', 'SUMMARY:DHCON', 'DTSTART:20270317T090000',
                                'DTEND:20270318T173000', 'LOCATION:Berlin', 'END:VEVENT', 'END:VCALENDAR']
    assert qr['payload'].event({'ev_title': 'x', 'ev_start': 'soon'}) == ''


def test_sepa_is_an_epc_code_and_refuses_a_bad_iban(qr):
    text = qr['payload'].sepa({'pay_name': 'Verein e.V.', 'pay_iban': 'de89 3704 0044 0532 0130 00', 'pay_bic': 'COBADEFFXXX', 'pay_amount': '12,5', 'pay_reference': 'Spende'})
    assert text.split('\n') == ['BCD', '002', '1', 'SCT', 'COBADEFFXXX', 'Verein e.V.', 'DE89370400440532013000', 'EUR12.50', '', '', 'Spende', '']
    assert qr['payload'].sepa({'pay_name': 'x', 'pay_iban': 'DE00'}) == ''
    assert qr['payload'].sepa({'pay_name': 'x', 'pay_iban': 'DE89370400440532013000', 'pay_amount': '-3'}) == ''


# --- What is drawn ------------------------------------------------------------------------------

def test_a_link_is_drawn_as_an_inline_svg(flask_app):
    html = render({'code': 'https://example.org', 'code__type': 'url'})
    assert html.startswith('<div class="dh-qrcode"') and '<svg' in html and 'viewBox' in html
    assert 'width:100%;height:100%' in html and '<script' not in html


def test_looks_are_applied_and_checked(flask_app):
    html = render({'code': 'hello', 'code__type': 'text', 'code__size': 20, 'code__fg': '#112233', 'code__bg': ''})
    assert 'height:20vh;width:20vh' in html and 'stroke="#123"' in html
    hostile = render({'code': 'https://x.org', 'code__fg': 'red" onload="alert(1)', 'code__bg': '#fff"><script>'})
    assert 'onload' not in hostile and '<script' not in hostile


def test_a_type_without_what_it_needs_draws_no_code(flask_app):
    assert '<svg' in render({'code': 'some text', 'code__type': 'text'})
    assert render({'code': '', 'code__type': 'url'}) == ''
    assert render({'code': '', 'code__type': 'wifi'}) == ''


def test_more_than_a_code_can_carry_draws_nothing(flask_app):
    assert render({'code': 'x' * 8000, 'code__type': 'url'}) == ''


def test_a_container_default_is_the_packed_values(flask_app):
    packed = json.dumps({'content': '', 'type': 'wifi', 'wifi_ssid': 'Guest', 'wifi_security': 'nopass'})
    assert '<svg' in render_default_value('qrcode', packed)
    assert render_default_value('qrcode', 'https://plain.example') .count('<svg') == 1       # a plain string is the link
