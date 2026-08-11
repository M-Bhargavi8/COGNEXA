def test_app_boots(app):
    assert app.config["TESTING"] is True


def test_db_is_empty_and_isolated(db, make_user):
    from gaminghub.models.user import User

    assert User.query.count() == 0
    make_user(username="alice")
    assert User.query.count() == 1


def test_client_can_hit_a_public_route(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_make_game_factory(make_game):
    game = make_game(slug="memory-matrix", category="brain-lab")
    assert game.slug == "memory-matrix"
    assert game.is_active is True
