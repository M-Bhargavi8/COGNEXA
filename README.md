# COGNEXA

**A full-stack cognitive gaming platform that turns every game you play into a measurable skill profile.**

COGNEXA is a Flask web app with 11 browser games. Eight of them, the **Brain Lab**, each measure one
cognitive skill. Every result feeds the player's skill profile, the leaderboards, achievements and
daily challenges. A token-authenticated REST API exposes the same data to other clients.

---

## Features

**Games**
- **Brain Lab** (8 games, 7 skills):

  | Game | Skill measured |
  |---|---|
  | Memory Matrix | Memory |
  | Reflex Lab | Reaction |
  | Focus Shift | Attention |
  | Sequence Breaker | Pattern Recognition |
  | Code Breaker | Logic |
  | Logic Grid | Logic |
  | Dual Task | Multitasking |
  | Risk & Reward | Decision Making |

- **Classic Arcade** (3 games): Guess the Number, Rock Paper Scissors, Tic Tac Toe.

**Progress and engagement**
- A per-player skill profile that shows the win rate for each skill, drawn on a radar chart.
- Global, daily, weekly, per-game and per-category leaderboards.
- XP and levels, an achievement catalogue, daily challenges and a daily reward claim.
- A shop for cosmetic items and XP boosters.
- A notification centre.

**Accounts**
- Registration with email verification, login with "keep me signed in", and safe `?next=` redirects.
- Forgot/reset password through single-use, expiring email links.
- Account settings: edit profile, change email (confirmed by link), and change password,
  which signs out every other device and revokes API tokens.

**Administration**
- An admin panel behind role-based access control.
- Users: search, details, suspend/deactivate/reactivate with a reason, role changes
  (the last admin is protected), and audited coin/XP adjustments.
- Games: edit names and descriptions, register missing games, enable/disable (a disabled game can't be played).
- Shop: create and edit items with server-side validation.
- An append-only audit log of admin and account-security actions.

## Security

- **Server-authoritative game state.** The server holds each game's state and the client sends only
  its moves. Each session can pay out only once, even under concurrent submissions.
- **Atomic balances.** Shop purchases and daily claims can't double-spend or double-claim.
- **CSRF protection** on every form, including logout. **Rate limiting** on login, registration,
  password reset and API token creation (shared through Redis in production).
- **Sessions** are invalidated everywhere on password change, reset or suspension. API tokens expire.
- **Strict CSP** with no inline script, Subresource Integrity on CDN assets, and the usual hardening headers.
- **Production config is validated at start-up.** The app refuses to start without a strong secret,
  an HTTPS base URL, shared rate-limit storage and real SMTP settings.

See [docs/SECURITY.md](docs/SECURITY.md) for the full review.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask 3, Flask-Login, Flask-WTF, Flask-Limiter, Flask-Bcrypt |
| Database | SQLAlchemy 2, PostgreSQL 16 (production) or SQLite (development), Alembic migrations |
| Server | Waitress, Docker, Redis (shared rate limits) |
| Frontend | Jinja2 templates, JavaScript, CSS |
| Testing | pytest (380+ tests, run on SQLite and PostgreSQL), ruff, GitHub Actions |

## Architecture

```
gaminghub/
├── routes/      # Flask blueprints: auth, games, brain_lab, leaderboard, analytics, admin, api, ...
├── services/    # Business logic: game, reward, achievement, challenge, leaderboard, analytics, shop
├── models/      # SQLAlchemy models: User, Game, GameSession, GameResult, Achievement, ...
├── templates/   # Jinja2 pages
└── static/      # CSS, JavaScript, audio
tests/           # pytest suite covering services, routes, the API and anti-cheat
migrations/      # Alembic migration history
```

Routes stay thin. The rules for scoring, rewards and achievements live in the `services/` layer,
so the web pages and the REST API share the same logic.

## REST API

To get a token, send a `POST` request to `/api/auth/token` with a JSON body of `{"email": ..., "password": ...}`.
Then add `Authorization: Bearer <token>` to every other request. Tokens expire after 30 days (the response
includes `expires_at`) and are revoked when the account's password changes.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/token`, `DELETE /api/auth/token` |
| Games | `GET /api/games`, `GET /api/games/<slug>` |
| Leaderboards | `GET /api/leaderboard/global` · `daily` · `weekly` · `game/<slug>` · `category/<category>` |
| Achievements & shop | `GET /api/achievements`, `GET /api/shop`, `POST /api/me/shop/buy/<item_id>` |
| Player | `GET /api/me`, `/me/results`, `/me/achievements`, `/me/analytics`, `/me/notifications` |
| Actions | `POST /api/me/notifications/<id>/read`, `/me/notifications/read-all`, `/me/daily-claim` |

`GET /api/` returns this list as JSON.

## Run it locally

```bash
git clone https://github.com/M-Bhargavi8/COGNEXA.git
cd COGNEXA
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env           # optional for local development
flask --app app db upgrade     # create or upgrade the database from the migrations
python seed_games.py           # load the games
python seed_achievements.py
python seed_shop_items.py
flask --app app promote-admin <your-username>   # after registering, to open the admin panel

python app.py                  # http://127.0.0.1:5000
```

In development, emails (verification and password reset) are written to the console log
instead of being sent (`MAIL_BACKEND=console`).

**Upgrading an existing database:** back it up first, then run `flask --app app db upgrade`.

## Tests and checks

```bash
pytest                         # SQLite
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/cognexa_test pytest   # PostgreSQL (disposable database)
ruff check .
```

CI (`.github/workflows/ci.yml`) runs lint, both test suites, a migration round trip on both
databases and a Docker smoke test on every push and pull request.

## Deployment

Production runs `wsgi:app` under Waitress, normally through the Docker image with PostgreSQL and Redis
(`docker-compose.yml`). Configuration, the first deployment, migrations, rollback and backup/restore are
covered in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Author

**Bhargavi Mudumbha**: [LinkedIn](https://www.linkedin.com/in/bhargavi-mudumbha) · [GitHub](https://github.com/M-Bhargavi8)
