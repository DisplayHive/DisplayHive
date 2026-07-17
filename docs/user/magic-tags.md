# Magic tags

Magic tags are simple, global name → value placeholders you can drop into
any template or content type HTML — useful for values that repeat across a
lot of content, like a Wi-Fi password or a venue name.

Manage them from the **Magic Tags** card on the **Templates** page
(`/templates`).

## Defining a tag

Create a magic tag with a name, a type, and an optional description to
remind editors what the tag is for.

The description isn't substituted into content — it's shown as a tooltip on
the tag chip when inserting tags into templates or content types.

### Text tags

A **Text** tag has a name and a value; the value is what gets rendered
wherever the tag is used, for example:

| Name | Value | Description |
|---|---|---|
| `wifi_password` | `Guest1234` | Guest Wi-Fi password shown on info screens |
| `venue_name` | `Hall B` | Display name of the venue/hall |

### List tags

A **List** tag doesn't hold its own value directly. Instead it points at a
**Magic Tag Value List** — a named set of key → value entries, managed in
the **Magic Tag Value Lists** card on the same page — and a key to look up
in that list. At render time, DisplayHive resolves the tag to the value of
the matching entry.

This is useful when several magic tags should share one editable table of
options — e.g. a "Rooms" value list with an entry per room, and one List
tag per template that just picks which room's entry to show:

| Value List `Rooms` | | |
|---|---|
| Key | Value |
| `hall_a` | `Hall A — Main Stage` |
| `hall_b` | `Hall B — Workshops` |

| Magic Tag | Type | Value List | Key |
|---|---|---|---|
| `current_room` | List | `Rooms` | `hall_a` |

Editing the value list's entries updates every List tag pointing at it
immediately, without having to edit each tag individually.

## Using a tag

Reference it in template or content-type HTML as `{{ var_<name> }}` (the
name is case-insensitive):

```html
<p>Wi-Fi password: {{ var_wifi_password }}</p>
```

At render time, DisplayHive substitutes the stored value.

!!! note "Why the `var_` prefix?"
    Template placeholders normally become **content containers** when you
    click "Extract tags" (see
    [Templates, containers & content](content-and-templates.md)). Prefixing
    a placeholder with `var_` tells DisplayHive to treat it as a magic tag
    instead — it's excluded from container extraction, and if a matching
    magic tag doesn't exist yet, one is created automatically (with the
    `var_` prefix stripped from its name).
