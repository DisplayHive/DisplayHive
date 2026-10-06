import pytest

from application.db_url import normalize_database_url


@pytest.mark.parametrize('url,expected', [
    ('postgresql://u:p@db:5432/x', 'postgresql+psycopg2://u:p@db:5432/x'),
    ('postgres://u:p@db/x', 'postgresql+psycopg2://u:p@db/x'),
    ('postgresql+psycopg://u:p@db/x', 'postgresql+psycopg://u:p@db/x'),
    ('postgresql+psycopg2://u:p@db/x', 'postgresql+psycopg2://u:p@db/x'),
    ('sqlite:///project.db', 'sqlite:///project.db'),
])
def test_normalize_database_url(url, expected):
    assert normalize_database_url(url) == expected
