from gaminghub.database.database import db
from gaminghub.models.game import Game
from gaminghub.models.game_session import GameSession
from gaminghub.config.constants import DIFFICULTIES, RPS_REWARD


def _seed_guess_game():
    game = Game(name="Guess The Number", slug="guess-the-number", category="classic-arcade", icon="🎯")
    db.session.add(game)
    db.session.commit()
    return game


def _seed_rps_game():
    game = Game(name="Rock Paper Scissors", slug="rock-paper-scissors", category="classic-arcade", icon="✊")
    db.session.add(game)
    db.session.commit()
    return game


class TestGuessTheNumber:

    def test_starting_a_session_picks_a_secret_within_range(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user()
            _seed_guess_game()
        login_as(user)

        client.post("/guess/start", data={"difficulty": "easy"}, follow_redirects=True)

        session = GameSession.query.filter_by(user_id=user.id, status="active").first()
        assert session is not None
        state = game_service_state(session)
        assert 1 <= state["secret"] <= 100
        assert state["attempts_left"] == DIFFICULTIES["easy"]["attempts"]

    def test_an_invalid_difficulty_is_rejected(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user()
            _seed_guess_game()
        login_as(user)

        resp = client.post("/guess/start", data={"difficulty": "impossible"}, follow_redirects=True)

        assert b"Invalid difficulty" in resp.data
        assert GameSession.query.filter_by(user_id=user.id).count() == 0

    def test_guessing_correctly_wins_and_grants_reward(self, app, client, make_user, login_as, db, monkeypatch):
        # guess-the-number's daily challenge template is satisfied by any
        # win and grants its own bonus xp/coins on top -- since
        # get_today_challenge() picks a template at random, this test would
        # occasionally (~1/11 runs) see inflated totals if that template
        # happened to be drawn. Deterministic without it.
        # random.choice() on an empty list raises IndexError -- needs a
        # non-empty list whose only entry references a slug nothing in
        # this test seeds, so get_today_challenge() finds no matching
        # Game and returns None, same as the real "no game seeded" path.
        from gaminghub.services import challenge_service
        monkeypatch.setattr(challenge_service, "CHALLENGE_TEMPLATES", [
            {"game_slug": "no-such-game", "difficulty": None, "criteria": {"type": "win"}, "xp": 1, "coins": 1, "description": "x"}
        ])

        with app.test_request_context():
            user = make_user(coins=0, xp=0)
            _seed_guess_game()
        login_as(user)

        client.post("/guess/start", data={"difficulty": "easy"}, follow_redirects=True)
        session = GameSession.query.filter_by(user_id=user.id, status="active").first()
        secret = game_service_state(session)["secret"]

        resp = client.post("/guess", data={"guess": str(secret)}, follow_redirects=True)

        assert b"Congratulations" in resp.data
        assert user.xp == DIFFICULTIES["easy"]["xp"]
        assert db.session.get(GameSession, session.id).status == "completed"

    def test_a_low_guess_gives_a_hint_and_does_not_end_the_game(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user()
            _seed_guess_game()
        login_as(user)

        client.post("/guess/start", data={"difficulty": "easy"}, follow_redirects=True)
        session = GameSession.query.filter_by(user_id=user.id, status="active").first()
        secret = game_service_state(session)["secret"]
        guess = secret - 1 if secret > 1 else secret + 1

        resp = client.post("/guess", data={"guess": str(guess)}, follow_redirects=True)

        assert (b"Too Low" in resp.data) or (b"Too High" in resp.data)
        assert db.session.get(GameSession, session.id).status == "active"

    def test_running_out_of_attempts_loses_and_reveals_the_answer(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user()
            _seed_guess_game()
        login_as(user)

        client.post("/guess/start", data={"difficulty": "easy"}, follow_redirects=True)
        session = GameSession.query.filter_by(user_id=user.id, status="active").first()
        secret = game_service_state(session)["secret"]
        wrong_guess = "1" if secret != 1 else "2"

        attempts = DIFFICULTIES["easy"]["attempts"]
        for _ in range(attempts):
            resp = client.post("/guess", data={"guess": wrong_guess}, follow_redirects=True)

        assert b"Game Over" in resp.data
        assert db.session.get(GameSession, session.id).status == "completed"

    def test_a_non_numeric_guess_does_not_crash(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user()
            _seed_guess_game()
        login_as(user)

        client.post("/guess/start", data={"difficulty": "easy"}, follow_redirects=True)
        resp = client.post("/guess", data={"guess": "not-a-number"}, follow_redirects=True)

        assert resp.status_code == 200
        assert b"valid number" in resp.data.lower()


class TestRockPaperScissors:

    def test_an_invalid_choice_is_rejected(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user()
            _seed_rps_game()
        login_as(user)

        resp = client.post("/rps", data={"choice": "Lizard"}, follow_redirects=True)

        assert b"Invalid choice" in resp.data

    def test_playing_produces_win_lose_or_draw_and_a_game_result(self, app, client, make_user, login_as, db):
        from gaminghub.models.game_result import GameResult

        with app.test_request_context():
            user = make_user()
            _seed_rps_game()
        login_as(user)

        resp = client.post("/rps", data={"choice": "Rock"}, follow_redirects=True)

        assert resp.status_code == 200
        assert any(word in resp.data for word in [b"YOU WIN", b"YOU LOST", b"DRAW"])
        assert GameResult.query.filter_by(user_id=user.id).count() == 1

    def test_a_win_grants_the_configured_reward(self, app, client, make_user, login_as, db, monkeypatch):
        """Playing Rock repeatedly against a random computer choice makes a
        win near-certain within 30 tries (P(never win) < 1e-5) without
        needing to control the RNG directly. The challenge template for
        this game is also satisfied by any win and would occasionally
        (~1/11 runs) inflate the expected reward if left un-mocked --
        same reasoning as the guess-the-number version of this test."""

        from gaminghub.services import challenge_service
        monkeypatch.setattr(challenge_service, "CHALLENGE_TEMPLATES", [
            {"game_slug": "no-such-game", "difficulty": None, "criteria": {"type": "win"}, "xp": 1, "coins": 1, "description": "x"}
        ])

        with app.test_request_context():
            user = make_user(coins=0, xp=0)
            _seed_rps_game()
        login_as(user)

        won_once = False
        for _ in range(30):
            resp = client.post("/rps", data={"choice": "Rock"}, follow_redirects=True)
            if b"YOU WIN" in resp.data:
                won_once = True
                break

        assert won_once, "Rock should have beaten Scissors at least once in 30 tries"
        assert user.xp == RPS_REWARD["xp"]
        assert user.coins == RPS_REWARD["coins"]


def game_service_state(session):
    import json
    return json.loads(session.state)
