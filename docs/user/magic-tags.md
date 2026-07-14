# Magic tags

Magic tags are simple, global name → value placeholders you can drop into
any template or content type HTML — useful for values that repeat across a
lot of content, like a Wi-Fi password or a venue name.

Manage them from the **Magic Tags** card on the **Templates** page
(`/templates`).

## Defining a tag

Create a magic tag with a name and a value, for example:

| Name | Value |
|---|---|
| `wifi_password` | `Guest1234` |
| `venue_name` | `Hall B` |

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
