# Security review (October 2026)

A focused review of the COGNEXA codebase covering authentication,
authorization, input handling, balance-sensitive operations, configuration
and dependencies. Every fix listed here has a regression test.

## Controls in place

| Area | Control |
|---|---|
| Passwords | bcrypt; 8 chars minimum, 72 bytes maximum (bcrypt's limit, enforced up front); no timing difference between unknown email and wrong password |
| Sessions | HttpOnly, SameSite=Lax, Secure in production; `auth_version` in the session id invalidates every session and remember-me cookie on password change/reset or suspension |
| Remember me | Opt-in, 14 days, HttpOnly, invalidated the same way |
| Password reset | 256-bit random tokens, stored as SHA-256, single use (conditional UPDATE), 1 h expiry, newest link only, 2-minute per-account email cooldown, identical response for unknown addresses, links built from `APP_BASE_URL` (never the Host header), token moved out of the URL on landing |
| Email verification | Same token scheme (48 h). An email change only takes effect after the new address is confirmed; the old address is notified |
| CSRF | Flask-WTF on every browser POST, including logout and the daily claim (now POST-only). The bearer-token API is exempt because it uses no cookies |
| Rate limits | Register 5/h; login 10/min; forgot-password POST 5/15 min; reset 10/15 min; resend 3/15 min; password change 5/15 min; API token 10/min. Shared via Redis in production, with per-process fallback |
| Authorization | Admin blueprint guarded at blueprint level and on each view; users can't change their own role or status; the last active admin can't be demoted or suspended; profile updates read only username/bio/country/favorite game |
| Audit | Append-only `audit_logs` table (no edit or delete routes) for admin actions and account-security events; never stores passwords or tokens |
| API tokens | SHA-256 at rest, 30-day expiry, revoked on password change/reset and suspension, refused for inactive accounts |
| Game integrity | Server-side game state (existing), plus a conditional UPDATE so a session can pay out only once even under concurrent submissions |
| Balances | Shop debit and daily claim are conditional UPDATEs; a unique constraint rolls back a racing duplicate purchase |
| Headers | CSP with **no inline script** (`script-src 'self' cdn.jsdelivr.net`), `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`; X-Frame-Options DENY; nosniff; Referrer-Policy; Permissions-Policy; COOP; HSTS over HTTPS; `Cache-Control: no-store` on pages |
| Third-party assets | Subresource Integrity (sha384) on Bootstrap and Chart.js |
| Redirects | `?next=` and notification links must be same-site relative paths (absolute, `//`, backslash and control-character tricks are rejected) |
| Errors and logs | Generic 500 pages and JSON errors; debug refused in production; request logs use route patterns, so URL tokens are never logged; inbound request IDs are sanitised |
| Config | Production refuses to start without a strong `SECRET_KEY`, explicit `DATABASE_URL`, `https://` base URL, shared rate-limit storage and real SMTP settings |
| Request size | 1 MB maximum body |

## Issues found and fixed

| # | Severity | Issue | Fix |
|---|---|---|---|
| 1 | High | Passwords over 72 bytes crashed registration and login with a 500 (bcrypt ≥ 5 raises) | Rejected at validation; login treats them as invalid |
| 2 | High | Concurrent submissions of one game session could pay the reward twice | Conditional `UPDATE … WHERE status='active'` decides the single winner |
| 3 | High | Concurrent purchases could spend the same coins twice | Conditional debit `WHERE coins >= cost`; IntegrityError rollback for duplicate ownership |
| 4 | Medium | Concurrent daily claims could both pay | Conditional `UPDATE … WHERE last_claim != today` |
| 5 | High (PostgreSQL) | `notifications.icon` was VARCHAR(10) but stored 11-char slugs; every achievement unlock would 500 on PostgreSQL | Migration `b7d1f3a92c4e` widens the column |
| 6 | Medium | Logout was a GET (cross-site logout) and the daily claim was a state-changing GET | Both are now CSRF-protected POSTs |
| 7 | Medium | Disabled games could still be opened and played through direct URLs | A central `before_request` guard blocks every endpoint of a disabled game |
| 8 | Medium | API tokens never expired and kept working after the account changed | Expiry, revocation on password change/suspension, inactive users refused |
| 9 | Medium | Legacy accounts whose emails differ only by case: a case-insensitive lookup could pick the wrong account | Exact match first; ambiguous case-insensitive matches resolve to nobody |
| 10 | Medium | Inline scripts forced `script-src 'unsafe-inline'` | Scripts moved to static files; data passed through JSON blocks and data attributes |
| 11 | Low | Werkzeug 3.1.8 (PYSEC-2026-4312, `safe_join` on Windows) | Upgraded to 3.1.9; `pip-audit` reports no known vulnerabilities |
| 12 | Low | A Redis outage would have failed every rate-limited request while `/healthz` stayed green | In-memory fallback, and `/healthz` reports `degraded` |
| 13 | Low | CDN assets had no integrity check | SRI hashes added |

## Remaining risks and recommendations

* **`style-src 'unsafe-inline'` remains.** About 75 `style="…"` attributes,
  some carrying server-computed widths, would need moving into classes.
  Style injection is much less dangerous than script injection, and script
  stays locked down. Recommended follow-up.
* **No per-account login lockout.** Limits are per IP. Per-account lockout
  lets attackers lock out victims, so add it only together with
  CAPTCHA or step-up checks. Consider breached-password checks (k-anonymity
  HIBP API) at registration and password change.
* **No two-factor authentication.** Recommended for administrator accounts first.
* **Legacy data:** the development database contains two accounts whose
  emails differ only by case, and two notification rows that point at deleted
  users. Both are handled safely, but they should be cleaned up, after which
  a unique index on `lower(email)` can be added.
* **Old secret in git history:** a hard-coded `SECRET_KEY` from before commit
  `e747ab1` is in the public history. Nothing uses it any more; never reuse
  it. Rewriting history isn't needed.
* **Brain Lab scripts use `innerHTML`** with server-generated game content
  only (no user-supplied text). Prefer `textContent` when touching those files.
* **Email deliverability** (SPF, DKIM, DMARC for the sender domain) has to be
  configured with the mail provider.
