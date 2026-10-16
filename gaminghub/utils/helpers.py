from flask import flash


def flash_game_outcome(outcome):
    """
    outcome is the dict returned by game_service.complete_session (or
    None, if the session wasn't active). Flashes personal-best,
    achievement-unlock, and daily-challenge-complete messages in one
    place instead of repeating this in every game route.
    """

    if not outcome:
        return

    if outcome.get("is_new_best"):
        flash("New personal best!", "success")

    for achievement in outcome.get("achievements_unlocked", []):
        flash(f"Achievement Unlocked: {achievement.title}", "success")

    challenge = outcome.get("challenge_completed")
    if challenge:
        flash(
            f"Daily Challenge Complete! +{challenge.xp_reward} XP · +{challenge.coin_reward} Coins",
            "success"
        )
