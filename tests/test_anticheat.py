"""
Regression tests for the tic-tac-toe fix from Phase 2: the board used to
be trusted from the client, so a crafted request could claim a win that
never happened. It's now server-side GameSession.state, and the client
can only ever submit a move *index* -- there's no field the route reads
that could inject a board at all. These tests exercise the full HTTP
route, not just the service layer already covered in test_game_service.py,
to prove the wiring holds end to end.
"""

from gaminghub.database.database import db as _db

from gaminghub.database.database import db
from gaminghub.models.game import Game
from gaminghub.models.game_session import GameSession
from gaminghub.services import game_service
from gaminghub.config.constants import TICTACTOE_REWARD


def _seeded_session_one_move_from_winning(user):
    """X has two in a row (0, 1); playing index 2 wins immediately."""
    game = Game(name="Tic Tac Toe", slug="tic-tac-toe", category="classic-arcade", icon="❌")
    db.session.add(game)
    db.session.commit()

    session = game_service.start_session(
        user, "tic-tac-toe",
        state={"board": ["X", "X", "", "O", "O", "", "", "", ""]}
    )
    return game, session


class TestTicTacToeCannotBeWonWithoutPlaying:

    def test_winning_move_grants_the_real_reward(self, app, client, make_user, login_as, db, monkeypatch):
        # tic-tac-toe's daily challenge template ({"type": "win"}) is
        # satisfied by this exact win and grants its own bonus xp/coins on
        # top -- get_today_challenge() picks a template at random, so
        # without this the test would occasionally (~1/11 runs) see
        # inflated totals depending on which template got drawn. A non-
        # empty list is required: random.choice() on an empty one raises.
        from gaminghub.services import challenge_service
        monkeypatch.setattr(challenge_service, "CHALLENGE_TEMPLATES", [
            {"game_slug": "no-such-game", "difficulty": None, "criteria": {"type": "win"}, "xp": 1, "coins": 1, "description": "x"}
        ])

        with app.test_request_context():
            user = make_user(coins=0, xp=0)
            _seeded_session_one_move_from_winning(user)
        login_as(user)

        resp = client.post("/tictactoe", data={"move": "2"}, follow_redirects=True)

        assert resp.status_code == 200
        assert user.xp == TICTACTOE_REWARD["xp"]
        assert user.coins == TICTACTOE_REWARD["coins"]

    def test_the_route_never_reads_a_client_supplied_board(self, app, client, make_user, login_as, db):
        """The historical vulnerability: even if a request smuggles in a
        'board' field claiming a win, the route has no code path that
        reads it -- only 'move' (a single cell index) is ever consulted."""
        with app.test_request_context():
            user = make_user(coins=0, xp=0)
            _seeded_session_one_move_from_winning(user)
        login_as(user)

        fake_winning_board = ["X", "X", "X", "X", "X", "X", "X", "X", "X"]
        resp = client.post(
            "/tictactoe",
            data={"move": "-1", "board": str(fake_winning_board)},  # move is invalid on purpose
            follow_redirects=True
        )

        assert resp.status_code == 200
        assert user.xp == 0  # an invalid move grants nothing, the smuggled board is never consulted
        assert user.coins == 0

    def test_occupied_cell_is_rejected_and_grants_nothing(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user(coins=0, xp=0)
            game, session = _seeded_session_one_move_from_winning(user)
        login_as(user)

        resp = client.post("/tictactoe", data={"move": "0"}, follow_redirects=True)  # cell 0 is already "X"

        assert b"Invalid move" in resp.data
        assert user.xp == 0
        assert _db.session.get(GameSession, session.id).status == "active"

    def test_out_of_range_move_is_rejected(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user(coins=0, xp=0)
            _seeded_session_one_move_from_winning(user)
        login_as(user)

        resp = client.post("/tictactoe", data={"move": "99"}, follow_redirects=True)

        assert b"Invalid move" in resp.data
        assert user.xp == 0

    def test_non_numeric_move_is_rejected_not_a_server_error(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user(coins=0, xp=0)
            _seeded_session_one_move_from_winning(user)
        login_as(user)

        resp = client.post("/tictactoe", data={"move": "not-a-number"}, follow_redirects=True)

        assert resp.status_code == 200
        assert b"Invalid move" in resp.data


class TestReplayProtection:

    def test_posting_again_after_the_game_is_won_grants_nothing_more(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user(coins=0, xp=0)
            game, session = _seeded_session_one_move_from_winning(user)
        login_as(user)

        client.post("/tictactoe", data={"move": "2"}, follow_redirects=True)  # wins, session now completed
        xp_after_win = user.xp
        coins_after_win = user.coins
        assert xp_after_win > 0

        # replay: session.status != "active" now, so the route's own guard
        # ("if request.method == POST and session.status == 'active'")
        # should make this POST a complete no-op even before it reaches
        # complete_session()'s own status check.
        resp = client.post("/tictactoe", data={"move": "5"}, follow_redirects=True)

        assert resp.status_code == 200
        assert user.xp == xp_after_win
        assert user.coins == coins_after_win

    def test_starting_a_fresh_game_after_winning_abandons_the_won_session(self, app, client, make_user, login_as, db):
        with app.test_request_context():
            user = make_user(coins=0, xp=0)
            game, session = _seeded_session_one_move_from_winning(user)
        login_as(user)

        client.post("/tictactoe", data={"move": "2"}, follow_redirects=True)
        won_session_id = session.id

        client.get("/tictactoe")  # GET with no active session starts a new one

        assert _db.session.get(GameSession, won_session_id).status == "completed"
        new_session = game_service.get_active_session(user, game)
        assert new_session is not None
        assert new_session.id != won_session_id
