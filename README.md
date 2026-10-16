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

**Administration**
- An admin panel for users, games and shop items, behind role-based access control.

## Security

- **Server-authoritative game state.** The server holds each game's state, and the client sends only
  its moves. A crafted request cannot claim a win that never happened; regression tests in
  `tests/test_anticheat.py` cover this.
- **CSRF protection** on every form (Flask-WTF).
- **Rate limiting** (Flask-Limiter), for example 10 requests per minute on API token creation.
- **Security headers,** including `Content-Security-Policy` and `X-Frame-Options: DENY`.
- **Password hashing** with bcrypt.
- **No secret in the source.** `SECRET_KEY` comes from the environment, or a random key is generated
  once into the gitignored `instance/` folder.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask 3, Flask-Login, Flask-WTF, Flask-Limiter, Flask-Bcrypt |
| Database | SQLAlchemy 2, SQLite, Alembic migrations (Flask-Migrate) |
| Frontend | Jinja2 templates, JavaScript, CSS |
| Testing | pytest (210 tests) |

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
Then add `Authorization: Bearer <token>` to every other request.

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
pip install -r requirements.txt

cp .env.example .env           # optional for local development
flask --app app db upgrade     # create the database from the migrations
python seed_games.py           # load the games
python seed_achievements.py
python seed_shop_items.py

python app.py                  # http://127.0.0.1:5000
```

## Tests

```bash
pytest
```

## Author

**Bhargavi Mudumbha**: [LinkedIn](https://www.linkedin.com/in/bhargavi-mudumbha) · [GitHub](https://github.com/M-Bhargavi8)
