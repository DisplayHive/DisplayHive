# Single sign-on (OpenID Connect)

Admins can log in with an OpenID Connect provider (Keycloak, Microsoft
Entra ID, Authentik, Google, …) instead of a DisplayHive password. You can
configure several providers; each gets its own button on the login page.

## How it behaves

- **The first login creates the account.** The account gets its name from the
  provider (`preferred_username`, otherwise the email address) and has
  **no groups**, so it has no rights. It can log in but only sees the
  Dashboard until an admin assigns groups on the **Users** page. The Users
  page lists such new accounts in a hint at the top.
- **Accounts are matched on the provider's user ID** (`sub`), never on name or
  email. Renaming someone at the provider doesn't create a second account,
  and an email address that matches an existing account doesn't take it over.
- **Rights stay in DisplayHive.** The provider only says who someone is.
  Groups and rights are managed on the Users page as usual.
- **SSO accounts have no password.** Password login is off for them. An admin
  can turn it on by giving the account a password in its **Edit User** dialog.
- **Sessions** are normal DisplayHive sessions (12 hours). Logging out of
  DisplayHive doesn't log you out at the provider, and removing someone at the
  provider ends their DisplayHive session only when it expires. **Deactivate
  the account on the Users page** to lock someone out right away.

## Setting up a provider

You need the `authproviders.manage` right (Superadmins have it).

1. Open **Settings → Login providers (SSO)** and click **Add provider**.
2. Enter a **Name** (the button text) and an **Identifier**. The identifier
   is part of the redirect URI and can't be changed later.
3. Copy the **Redirect URI** shown in the dialog, e.g.
   `https://signage.example.com/admin/api/auth/oidc/company-sso/callback`.
4. At your provider, create a client (application) for DisplayHive:
    - type: confidential / web application, using the **authorization code** flow
    - redirect URI: the one you just copied
    - note down its **client ID** and **client secret**
5. Back in DisplayHive, enter the **Issuer URL** and click **Test**.
   DisplayHive loads `<issuer>/.well-known/openid-configuration` and reports
   what it found.
6. Enter the client ID and secret, then save. The button appears on the login page.

The client secret is stored in the database and never shown again. Leave the
field empty when editing to keep it.

!!! warning "Behind a reverse proxy"
    The redirect URI is built from the address the browser uses. Behind nginx
    or similar, set `TRUSTED_PROXY_COUNT` (see
    [Installation](installation.md#configuration)). Otherwise DisplayHive
    sends the provider an `http://` or internal-host redirect URI, and the
    provider rejects the login.

### Provider examples

| Provider | Issuer URL | Notes |
| --- | --- | --- |
| Keycloak | `https://keycloak.example.com/realms/<realm>` | Client authentication **on**, standard flow **on**. Add the redirect URI under *Valid redirect URIs*. |
| Microsoft Entra ID | `https://login.microsoftonline.com/<tenant-id>/v2.0` | App registration → *Web* platform → redirect URI. Create a client secret under *Certificates & secrets*. |
| Authentik | `https://authentik.example.com/application/o/<app-slug>/` | OAuth2/OpenID provider, client type *Confidential*. Keep the trailing slash. |
| Google | `https://accounts.google.com` | OAuth client of type *Web application*. Note: anyone with a Google account can log in and get an (empty) account. |

Scopes default to `openid profile email`. `openid` is always added.

## Linking SSO logins to existing accounts

Only admins can link SSO logins to accounts. The provider's user ID isn't
known until someone has logged in once, so it works like this:

1. The person logs in with SSO once. That creates a new, empty account.
2. On the **Users** page, click **Merge into existing user…**
   (<span title="arrows icon">⇄</span>) on that new account and pick their
   existing account.
3. The SSO login moves onto the existing account, and the empty account is
   deleted. From then on their SSO login opens their usual account.

The merge button only appears on accounts an SSO login created (those without
a password), so a real account can't be merged away by mistake. To detach
an SSO login again, open **Edit User** and click **Unlink** next to it. Its
next login then creates a new account.

## Password login as a fallback

Every account has an **Allow login with username and password** setting.
At least one active Superadmin always keeps password login, so you can still
get in when a provider is down or misconfigured. DisplayHive refuses any
change that would remove the last one: turning off password login,
deactivating or deleting the account, or changing its groups.

If you're locked out anyway, reset a password on the server with
[`flask dh reset-password <name> --activate`](cli.md#reset-password-username).
