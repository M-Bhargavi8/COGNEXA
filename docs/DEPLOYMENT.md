# Deploying COGNEXA

This guide covers production configuration, first deployment, upgrades
and migrations, rollback, and backup/restore.

**Status:** the configuration, Docker image and procedures below were
exercised end to end on a local Docker host (app + PostgreSQL 16 +
Redis 7). The project has **not** been deployed to a public host; that
step needs a hosting account, a domain with TLS and an SMTP provider.

## 1. Architecture

```
            HTTPS
browser ──► TLS proxy / platform router ──► waitress (wsgi:app, N threads)
                                               │
                         ┌─────────────────────┼─────────────────────┐
                    PostgreSQL 16          Redis 7               SMTP relay
                  (all app data)     (rate-limit counters)   (reset/verify mail)
```

* **WSGI server:** [Waitress](https://docs.pylonsproject.org/projects/waitress/),
  pure Python, so it runs on both Linux and Windows. Entry point: `wsgi:app`.
  `wsgi.py` defaults `APP_ENV` to `production`, so the strict checks always
  apply to a production start.
* **Database:** PostgreSQL is recommended (CI tests every change against it).
  SQLite on a persistent volume also works for a single instance.
* **Redis:** shared rate-limit storage. Needed once more than one process or
  instance serves traffic. If Redis becomes unreachable, the app falls back to
  per-process limits and `/healthz` reports `degraded`.
* **TLS** terminates in front of the app. Set `TRUSTED_PROXY_COUNT` to the
  number of proxies so client IPs (rate limiting) and HTTPS detection
  (secure cookies, HSTS) are correct.

## 2. Configuration reference

Every setting comes from the environment. `.env.example` lists all of them.
`ProductionConfig.validate()` refuses to start (and names each problem)
when a required value is missing or unsafe.

| Variable | Production | Purpose |
|---|---|---|
| `APP_ENV` | `production` (default in `wsgi.py` and the Docker image) | Selects the config class |
| `SECRET_KEY` | **Required**, ≥ 32 random chars | Signs sessions, CSRF tokens and remember-me cookies |
| `APP_BASE_URL` | **Required**, `https://…` | The only origin used in emailed links (never the Host header) |
| `DATABASE_URL` | **Required** | `postgresql://user:pass@host:5432/db` (or `postgres://…`), or `sqlite:////data/cognexa.db` |
| `RATELIMIT_STORAGE_URI` | **Required** unless single-process | `redis://host:6379/0` |
| `RATELIMIT_ALLOW_MEMORY_STORAGE` | `1` only for one process | Opt-in to per-process counters |
| `RATELIMIT_IN_MEMORY_FALLBACK_ENABLED` | `1` (default) | Keep limiting locally if Redis is down |
| `MAIL_BACKEND` | `smtp` (or `disabled`) | `console` is refused in production |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD` | Required for `smtp` | SMTP relay credentials |
| `MAIL_USE_TLS` / `MAIL_USE_SSL` | `1` / `0` typical (port 587) | STARTTLS or implicit TLS (port 465) |
| `MAIL_DEFAULT_SENDER` | Required, real address | e.g. `COGNEXA <no-reply@your-domain>` |
| `EMAIL_VERIFICATION_REQUIRED` | Product decision (default `0`) | `1` blocks login and API tokens until the email is verified |
| `TRUSTED_PROXY_COUNT` | Number of proxies (often `1`) | Trust `X-Forwarded-For/Proto/Host` from that many hops |
| `SESSION_COOKIE_SECURE` | `1` (default in production) | HTTPS-only cookies |
| `REMEMBER_COOKIE_DAYS` | `14` | "Keep me signed in" lifetime |
| `PASSWORD_RESET_TOKEN_MAX_AGE` | `3600` | Seconds a reset link stays valid |
| `EMAIL_VERIFICATION_TOKEN_MAX_AGE` | `172800` | Seconds a verification link stays valid |
| `API_TOKEN_TTL_DAYS` | `30` | API bearer-token lifetime |
| `LOG_LEVEL` | `INFO` | Production logs are JSON lines on stdout |
| `WAITRESS_THREADS`, `PORT` | `8` / `8000` | Server sizing (Docker/Procfile) |

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### What you need to supply (external)

1. **Hosting** that runs a container (or a Python process) and gives you a
   TLS endpoint, e.g. a VPS with Docker plus Caddy or Nginx, Render, Fly.io,
   Railway, or Azure App Service.
2. **PostgreSQL 16** (managed, or the `db` service in `docker-compose.yml`).
3. **Redis 7** if you run more than one process or instance.
4. **An SMTP provider** (Amazon SES, Postmark, SendGrid, Mailgun, …): host,
   port, username, password, and a verified sender domain or address.
5. **A domain name** for `APP_BASE_URL`.

## 3. First deployment (Docker Compose)

```bash
cp .env.example .env.production        # fill in real values; never commit it
docker compose --env-file .env.production up -d db redis
docker compose --env-file .env.production run --rm web flask --app wsgi db upgrade
docker compose --env-file .env.production run --rm web python seed_games.py
docker compose --env-file .env.production run --rm web python seed_achievements.py
docker compose --env-file .env.production run --rm web python seed_shop_items.py
docker compose --env-file .env.production up -d web
curl -fsS http://localhost:8000/healthz      # {"status":"ok"}
```

Put your TLS proxy in front of port 8000 and set `TRUSTED_PROXY_COUNT=1`.

**First administrator:** register normally, then promote that account once
from a shell (no admin exists yet to do it through the UI):

```bash
docker compose --env-file .env.production run --rm web flask --app wsgi promote-admin YOUR_USERNAME
```

The promotion is recorded in the audit log.

### Without Docker (platform with a Procfile)

`Procfile` declares `release: flask --app wsgi db upgrade` and
`web: waitress-serve … wsgi:app`. Set the environment variables in the
platform's dashboard and run the three seed scripts once after the first release.

### Single instance on SQLite

```
DATABASE_URL=sqlite:////data/cognexa.db
RATELIMIT_ALLOW_MEMORY_STORAGE=1
```

Mount a persistent volume at `/data`. Run exactly one container.

## 4. Upgrading (new release)

1. **Back up the database** (section 6). Don't migrate production without a fresh backup.
2. Build or pull the new image.
3. Run migrations explicitly; they never run implicitly at start-up:
   `docker compose --env-file .env.production run --rm web flask --app wsgi db upgrade`
4. Restart the app: `docker compose --env-file .env.production up -d web`
5. Check `GET /healthz` and the logs.

`flask --app wsgi db current` shows the applied revision and
`flask --app wsgi db history` lists all of them.

### Migrations in this release

| Revision | Change | Data impact |
|---|---|---|
| `a4c2e8f61b90` | Account status, email verification, auth_version, password_changed_at on `users`; new `account_tokens` and `audit_logs` tables; `api_tokens.expires_at`; two indexes | Existing users stay `active` with `auth_version=0` (existing sessions keep working) and **unverified**. Existing API tokens get a 30-day expiry from the time of the upgrade. |
| `b7d1f3a92c4e` | Widen `notifications.icon` and `users.equipped_badge` to 30 chars | None. Required for PostgreSQL. |

Both were tested on a fresh SQLite database, on a copy of the development
database (all rows preserved), and on PostgreSQL 16: upgrade, `flask db check`
(no drift), downgrade to base, and upgrade again.

## 5. Rollback

**Application only (no schema change in the release):** redeploy the previous
image tag.

**Release that included migrations:**

1. Stop the web process.
2. Either **downgrade** to the previous revision:
   `flask --app wsgi db downgrade <previous_revision>`
   (e.g. `e91a4c6f2b83` to undo both migrations above), **or** restore the
   backup taken before the upgrade (section 6). Restoring is safest if the new
   version has already written data that relies on the new columns.
3. Deploy the previous image and start it.

Downgrading `a4c2e8f61b90` drops the account-token, audit-log and status
columns, so audit history and suspensions are lost. Take a backup first.

Validated locally: downgrading `b7d1f3a92c4e` and upgrading again on the
Compose stack kept the app healthy and every row intact.

## 6. Backup and restore

### PostgreSQL

```bash
# Backup (custom format, compressed)
docker compose --env-file .env.production exec -T db pg_dump -U cognexa -d cognexa -Fc > cognexa-$(date +%F).dump

# Restore into a new, empty database
docker compose --env-file .env.production exec -T db createdb -U cognexa cognexa_restore
docker compose --env-file .env.production exec -T db pg_restore -U cognexa -d cognexa_restore --no-owner < cognexa-YYYY-MM-DD.dump
```

Point `DATABASE_URL` at the restored database (or rename it) and restart.
Validated locally: a dump restored into a fresh database matched row counts
and coin totals exactly. With managed PostgreSQL, also turn on the
provider's automated backups and point-in-time recovery.

### SQLite

Stop the app (or use the online backup API) and copy the file:

```bash
sqlite3 /data/cognexa.db ".backup '/backups/cognexa-$(date +%F).db'"
```

Restore by stopping the app and replacing the file.

Store backups off the host, encrypt them (they hold email addresses and
password hashes), and **test a restore regularly**. A backup nobody has
restored is unverified.

## 7. Operations

* **Health:** `GET /healthz` returns `200 {"status":"ok"}`,
  `200 {"status":"degraded"}` (rate-limit storage down; app still serving),
  or `503 {"status":"unavailable"}` (database down). The Docker image has a
  `HEALTHCHECK` built in.
* **Logs:** JSON lines on stdout with `request_id`, method, route pattern,
  status and duration. Request logs record the route pattern
  (`/reset-password/<token>`), never the raw URL, so tokens don't reach logs.
  An inbound `X-Request-ID` is reused if it is a plain token.
* **Static files** are served by the app. For heavy traffic, put a CDN or the
  proxy's static file serving in front of `/static/`.
* **Uploads:** none. No feature accepts files, and request bodies are capped
  at 1 MB.
* **Secrets:** an old hard-coded `SECRET_KEY` exists in early git history
  (removed in commit `e747ab1`). Never reuse it; always generate a new key.

## 8. CI

`.github/workflows/ci.yml` runs on every push to `main` and on every pull request:

* `ruff check`
* the test suite on SQLite and on PostgreSQL 16
* migrations on both databases: fresh upgrade, `flask db check`, seeds,
  downgrade to base, and upgrade again
* Docker build, then a production-config smoke test (`/healthz`, pages,
  refusal of an unsafe config)

CI uses no repository secrets; the test database password and the smoke-test
key are throwaway values. Deployment automation is deliberately not included
yet. Add it once a host exists and this rollback procedure has been rehearsed there.
