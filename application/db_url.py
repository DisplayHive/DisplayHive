"""DATABASE_URL handling shared by the app and Alembic."""


def normalize_database_url(url: str) -> str:
    """Make the PostgreSQL driver explicit (psycopg2).

    A bare ``postgresql://`` URL leaves the driver choice to SQLAlchemy, whose
    default changed between releases (psycopg2 in 2.0, psycopg 3 in 2.1) — an
    unpinned image build then fails with "No module named 'psycopg'" although
    psycopg2 is what we install. Naming the driver makes the result independent
    of that. URLs that already name a driver (``postgresql+psycopg://``…) and
    non-PostgreSQL URLs are left alone.
    """
    for prefix in ('postgresql://', 'postgres://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg2://' + url[len(prefix):]
    return url
