"""Declarative registry of primary/independently-selectable entity types.

Drives both the export/import selection tree (one node per entity type,
expandable to individual items) and the dependency-closure resolution used
by ``helper.py`` — selecting an entity that hard-depends on another (e.g. a
Contenttype's Layout) automatically pulls that dependency in too, so any
export/import is always self-consistent.

Only entities that can be independently selected/matched across instances
carry a `uuid` column and appear here. Support/child rows (DesignGradient,
DesignContainerStyle, DesignGlobalStyle, TagConfig,
MagicTagValueListEntry, and the pure association tables) always ride along
with their owning entity and are not part of this registry.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EntityType:
    key: str
    model_name: str  # resolved lazily via get_model() to avoid a hard import at module load
    label_field: str
    depends_on: tuple = field(default_factory=tuple)


# Declared in dependency-safe order: a type never depends_on a type that
# appears later in this list (import_database relies on this ordering).
ENTITY_TYPES = [
    EntityType(key='screens', model_name='Screen', label_field='name', depends_on=()),
    EntityType(key='screengroups', model_name='Screengroup', label_field='name', depends_on=()),
    EntityType(key='gradients', model_name='Gradient', label_field='name', depends_on=()),
    EntityType(key='contentcontainers', model_name='ContentContainer', label_field='name', depends_on=()),
    # Design's support rows (DesignGradient / DesignContainerStyle) reference
    # Gradient/ContentContainer, so both must be resolvable before Design.
    EntityType(key='designs', model_name='Design', label_field='name', depends_on=('gradients', 'contentcontainers')),
    EntityType(key='layouts', model_name='Layout', label_field='name', depends_on=('contentcontainers',)),
    EntityType(key='contenttypes', model_name='Contenttype', label_field='name', depends_on=('layouts',)),
    EntityType(key='content_elements', model_name='ContentElement', label_field='title', depends_on=('contenttypes',)),
    EntityType(key='media', model_name='Media', label_field='filename', depends_on=()),
    EntityType(key='devices', model_name='Device', label_field='name', depends_on=()),  # screen link is soft/nullable, not a hard dep
    EntityType(key='magic_tag_value_lists', model_name='MagicTagValueList', label_field='name', depends_on=()),
    EntityType(key='magic_tags', model_name='MagicTag', label_field='name', depends_on=('magic_tag_value_lists',)),  # only when value_list_id set
]

ENTITY_TYPES_BY_KEY = {et.key: et for et in ENTITY_TYPES}


def get_model(entity_type: EntityType):
    """Resolve an EntityType's SQLAlchemy model class (deferred import to avoid
    circular-import issues at module load time)."""
    from application import models
    return getattr(models, entity_type.model_name)


def dependency_types_of(key: str) -> tuple:
    """The tuple of entity-type keys `key` hard-depends on (empty if none)."""
    et = ENTITY_TYPES_BY_KEY.get(key)
    return et.depends_on if et else ()
