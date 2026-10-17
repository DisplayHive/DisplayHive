"""What a field handler is, as far as the host and the plugins agree on it.

A field handler decides how one field of a content type is shown on a screen. Its id (``countdown``)
is what the data stores (``TagConfig.field_handler``) and never changes; the code behind it lives in a
plugin. The host builds a :class:`RenderContext` for every field of a content element and asks the
handler for the field's HTML.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RenderContext:
    """Everything a handler may look at while rendering one field.

    ``values`` is the content element's flat key bag (``<name>``, ``<name>__<suffix>``); a handler only
    reads the keys of its own field.
    """
    field_name: str
    values: dict
    db: Any = None                                  # SQLAlchemy ``db`` or None (previews without a database)
    tagconfig: Any = None

    @property
    def value(self):
        """The field's own value (``None`` when nothing was stored)."""
        return self.values.get(self.field_name)

    @property
    def has_value(self) -> bool:
        """True when the field has a non-empty value."""
        return self.field_name in self.values and bool(self.values[self.field_name])

    def option(self, suffix: str, default=None):
        """The field's ``<name>__<suffix>`` value."""
        return self.values.get(f'{self.field_name}__{suffix}', default)


class FieldHandler:
    """Base class of a field handler. A plugin subclasses it and registers an instance."""

    #: The id stored in ``TagConfig.field_handler`` (and in exports): stable, lower case.
    id: str = ''
    #: A scene that uses this handler is rendered again after it was shown (live data, e.g. a schedule).
    refresh_after_show: bool = False

    def render(self, rc: RenderContext) -> Optional[str]:
        """The field's HTML. Return ``None`` to leave the stored value as it is (plain pass-through)."""
        return None

    def default_values(self, packed: str) -> dict:
        """Turn a container's packed default content into the flat key bag the field would have stored.

        ``packed`` is ``ContentContainer.default_content``: a plain value for most handlers, JSON for
        those whose value has several parts. The key of the field itself is ``default``.
        """
        return {'default': packed}


@dataclass
class Provided:
    """What one plugin has put into the registry (so unloading it can take everything back)."""
    plugin_id: str
    fieldhandlers: list = field(default_factory=list)


class DataSection:
    """Data a plugin owns that export and import carry along ("if selected").

    A section is one node in the export/import selection tree, with the plugin's rows as items. Rows are
    plain JSON-able dicts; each has a ``uuid`` so the same row can be recognised on another instance.
    """

    #: Unique in the instance; the key under ``plugin_data`` in the export file.
    id: str = ''
    #: The node's name in the selection tree.
    label: str = ''

    def items(self, db) -> list:
        """``[{'uuid': …, 'label': …}]``: what can be selected."""
        return []

    def existing_uuids(self, db) -> set:
        """The uuids of the rows this instance has already (an import marks those that would clash)."""
        return set()

    def export_rows(self, db, uuids=None) -> list:
        """The rows to export (only those whose uuid is in *uuids*; all when it is ``None``)."""
        return []

    def import_rows(self, db, rows: list, mode: str, conflict_resolution: str) -> int:
        """Write *rows* (as exported). ``mode`` is ``reset`` or ``merge``; in merge mode ``conflict_resolution``
        says what to do with a row that exists already (``skip`` or ``overwrite``). Returns the number written."""
        return 0

    def clear(self, db) -> None:
        """Delete the section's rows (an import in reset mode starts from nothing)."""
