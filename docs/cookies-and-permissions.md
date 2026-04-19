# Browser Cookies and Permissions

AI Quota Bar reads a small allowlisted set of browser cookies so it can call the same usage endpoints your browser session already uses for Claude, ChatGPT, Cursor, and GitHub Copilot.

This app does not install a browser extension, inject code into web pages, or send cookies to unrelated services. It reads cookies locally on your Mac, keeps the filtered values in the macOS Keychain, and uses them only for the matching provider's usage requests.

## Exactly Which Cookies Are Read

| Provider | Cookies AI Quota Bar reads | When it reads them | Why |
|---|---|---|---|
| Claude | `sessionKey`, `lastActiveOrg`, `routingHint`, `cf_clearance`, `__cf_bm`, `_cfuvid` | Auto-detected on startup, or when you manually refresh Claude auth | `sessionKey` authenticates the session. `lastActiveOrg` or `routingHint` identifies the org whose usage is shown. Claude Cloudflare cookies may be present in the browser jar and are retained if found during detection. |
| ChatGPT | `__Secure-next-auth.session-token` | Only after you explicitly enable ChatGPT | Used to exchange your browser session for a short-lived ChatGPT access token before usage is fetched. |
| Copilot | `user_session`, `logged_in`, `dotcom_user` | Only after you explicitly enable Copilot | Used to request GitHub Copilot premium request usage from your signed-in GitHub session. |
| Cursor | `WorkosCursorSessionToken` | Only after you explicitly enable Cursor | Used to request Cursor usage from your signed-in Cursor session. |

## What The App Does With Those Cookies

1. It reads the browser's local cookie store for the relevant provider domain.
   It does that through a short-lived helper launch so browser access stays isolated from the menu bar UI process.
2. It filters the result down to the provider-specific allowlist above.
3. It saves that filtered cookie string in the macOS Keychain, not in plaintext config.
4. It sends the cookie only to the matching provider endpoint needed to fetch usage data.
5. It does not log raw cookie values.

Current provider requests:

- Claude: uses the Claude session to look up your org and fetch usage from `claude.ai`.
- ChatGPT: calls `chatgpt.com/api/auth/session`, then `chatgpt.com/backend-api/wham/usage`.
- Copilot: calls `github.com/settings/billing/copilot_usage_card`.
- Cursor: calls `cursor.com/api/usage-summary`.

For Claude, Cloudflare cookies may be captured if they exist in the browser jar, but they are stripped before the app sends its requests.

## Why macOS Asks For "Always Allow"

On macOS, browsers often protect saved cookies with system-managed storage. For Chromium-family browsers, that can include Keychain items such as the browser's safe-storage secret, which is used to decrypt the cookie database locally.

When AI Quota Bar reads those cookies, macOS may ask whether the app is allowed to use that browser-protected secret. Choosing `Always Allow` is what makes the setup truly one-time:

- `Always Allow`: AI Quota Bar can refresh usage in the background without showing the same permission prompt again.
- `Allow`: macOS may ask again on the next refresh.
- `Deny`: cookie auto-detection will fail until permission is granted.

That permission is for local cookie access on your Mac. It does not grant AI Quota Bar broader browser control, page access, or permission to send your cookies anywhere except the matching provider request needed for usage checks.
