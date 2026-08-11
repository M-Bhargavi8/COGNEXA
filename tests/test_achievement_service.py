from gaminghub.services import achievement_service


class TestUnlock:

    def test_unlocking_grants_rewards_and_records_it(self, make_user, make_achievement):
        make_achievement("First Game", coin_reward=20, xp_reward=5)
        user = make_user(coins=0)

        achievement = achievement_service.unlock(user, "First Game")

        assert achievement is not None
        assert user.coins == 20
        assert user.xp == 5

    def test_unlocking_an_unknown_name_returns_none(self, make_user):
        user = make_user()
        assert achievement_service.unlock(user, "Nonexistent Achievement") is None

    def test_unlocking_twice_is_a_no_op_the_second_time(self, make_user, make_achievement):
        make_achievement("First Game", coin_reward=20)
        user = make_user(coins=0)

        first = achievement_service.unlock(user, "First Game")
        second = achievement_service.unlock(user, "First Game")

        assert first is not None
        assert second is None
        assert user.coins == 20  # not double-granted


class TestCheckAchievements:

    def test_unlocks_first_game_at_one_play(self, make_user, make_achievement):
        make_achievement("First Game")
        user = make_user(games_played=1)

        unlocked = achievement_service.check_achievements(user)

        assert [a.name for a in unlocked] == ["First Game"]

    def test_unlocks_rising_star_at_level_five(self, make_user, make_achievement):
        make_achievement("Rising Star")
        user = make_user(level=5)

        unlocked = achievement_service.check_achievements(user)

        assert "Rising Star" in [a.name for a in unlocked]

    def test_does_not_unlock_rising_star_below_level_five(self, make_user, make_achievement):
        make_achievement("Rising Star")
        user = make_user(level=4)

        unlocked = achievement_service.check_achievements(user)

        assert unlocked == []

    def test_unlocks_rich_player_at_500_coins(self, make_user, make_achievement):
        make_achievement("Rich Player")
        user = make_user(coins=500)

        unlocked = achievement_service.check_achievements(user)

        assert "Rich Player" in [a.name for a in unlocked]

    def test_unlocks_week_streak_at_seven_days(self, make_user, make_achievement):
        make_achievement("7 Day Streak")
        user = make_user(daily_streak=7)

        unlocked = achievement_service.check_achievements(user)

        assert "7 Day Streak" in [a.name for a in unlocked]

    def test_checks_multiple_thresholds_in_one_call(self, make_user, make_achievement):
        make_achievement("First Game")
        make_achievement("Gamer")
        user = make_user(games_played=10)

        unlocked = {a.name for a in achievement_service.check_achievements(user)}

        assert unlocked == {"First Game", "Gamer"}


class TestCheckGameAchievements:

    def test_brain_trainer_unlocks_for_any_brain_lab_game(self, make_user, make_game, make_achievement, db):
        from gaminghub.models.game_result import GameResult
        from gaminghub.models.game_session import GameSession

        make_achievement("Brain Trainer")
        user = make_user()
        game = make_game(slug="memory-matrix", category="brain-lab")
        session = GameSession(user_id=user.id, game_id=game.id, status="completed", state="{}")
        db.session.add(session)
        db.session.commit()
        result = GameResult(user_id=user.id, game_id=game.id, game_session_id=session.id, result="win", score=1)
        db.session.add(result)
        db.session.commit()

        unlocked = achievement_service.check_game_achievements(user, result)

        assert "Brain Trainer" in [a.name for a in unlocked]

    def test_brain_trainer_does_not_unlock_for_a_classic_game(self, make_user, make_game, make_achievement, db):
        from gaminghub.models.game_result import GameResult
        from gaminghub.models.game_session import GameSession

        make_achievement("Brain Trainer")
        user = make_user()
        game = make_game(slug="guess-the-number", category="classic-arcade")
        session = GameSession(user_id=user.id, game_id=game.id, status="completed", state="{}")
        db.session.add(session)
        db.session.commit()
        result = GameResult(user_id=user.id, game_id=game.id, game_session_id=session.id, result="win", score=1)
        db.session.add(result)
        db.session.commit()

        unlocked = achievement_service.check_game_achievements(user, result)

        assert unlocked == []

    def test_perfect_recall_needs_memory_matrix_and_full_accuracy(self, make_user, make_game, make_achievement, db):
        from gaminghub.models.game_result import GameResult
        from gaminghub.models.game_session import GameSession

        make_achievement("Perfect Recall")
        user = make_user()
        game = make_game(slug="memory-matrix", category="brain-lab")
        session = GameSession(user_id=user.id, game_id=game.id, status="completed", state="{}")
        db.session.add(session)
        db.session.commit()
        result = GameResult(user_id=user.id, game_id=game.id, game_session_id=session.id, result="win", score=1, accuracy=1.0)
        db.session.add(result)
        db.session.commit()

        unlocked = achievement_service.check_game_achievements(user, result)

        assert "Perfect Recall" in [a.name for a in unlocked]

    def test_speed_demon_needs_reflex_lab_under_250ms(self, make_user, make_game, make_achievement, db):
        from gaminghub.models.game_result import GameResult
        from gaminghub.models.game_session import GameSession

        make_achievement("Speed Demon")
        user = make_user()
        game = make_game(slug="reflex-lab", category="brain-lab")
        session = GameSession(user_id=user.id, game_id=game.id, status="completed", state="{}")
        db.session.add(session)
        db.session.commit()
        result = GameResult(user_id=user.id, game_id=game.id, game_session_id=session.id, result="win", score=1, reaction_time=200)
        db.session.add(result)
        db.session.commit()

        unlocked = achievement_service.check_game_achievements(user, result)

        assert "Speed Demon" in [a.name for a in unlocked]

    def test_speed_demon_does_not_unlock_at_250ms_or_slower(self, make_user, make_game, make_achievement, db):
        from gaminghub.models.game_result import GameResult
        from gaminghub.models.game_session import GameSession

        make_achievement("Speed Demon")
        user = make_user()
        game = make_game(slug="reflex-lab", category="brain-lab")
        session = GameSession(user_id=user.id, game_id=game.id, status="completed", state="{}")
        db.session.add(session)
        db.session.commit()
        result = GameResult(user_id=user.id, game_id=game.id, game_session_id=session.id, result="win", score=1, reaction_time=250)
        db.session.add(result)
        db.session.commit()

        unlocked = achievement_service.check_game_achievements(user, result)

        assert unlocked == []
