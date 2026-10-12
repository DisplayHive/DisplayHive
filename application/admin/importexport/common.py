"""Pieces shared by the export and import halves: the allowlist of exportable
system settings and the lazily imported support (association) models."""


# SystemSetting is a flat key/value store (no uuid, not independently
# selectable), so it rides along with every export/import as a single blob
# rather than through the registry/ENTITY_TYPES machinery. Only an explicit
# allowlist of known-safe, non-secret keys is ever exported or imported —
# secrets such as 'telegram_token' (application/admin/alerting/sockethandlers.py)
# must never leave the instance in an export file. Reuses the same allowlist
# the generic Settings-page write endpoint already trusts, plus the one
# other known-safe key (layout snap lines) that has its own dedicated handler.
def _exportable_setting_keys():
    from application.admin.settings.sockethandlers import ALLOWED_SETTING_KEYS
    return ALLOWED_SETTING_KEYS | {'layout_snaplines'}


def _support_models():
    from application.models import TagConfig
    from application.models.base import screengroup_screen, content_element_screengroup
    from application.models.content import (
        layout_container, DesignGradient, DesignContainerStyle, DesignGlobalStyle,
    )
    return dict(
        TagConfig=TagConfig,
        screengroup_screen=screengroup_screen, content_element_screengroup=content_element_screengroup,
        layout_container=layout_container, DesignGradient=DesignGradient,
        DesignContainerStyle=DesignContainerStyle, DesignGlobalStyle=DesignGlobalStyle,
    )


# ---------------------------------------------------------------------------
