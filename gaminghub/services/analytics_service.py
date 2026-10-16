from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func

from gaminghub.database.database import db
from gaminghub.models.game import Game
from gaminghub.models.game_result import GameResult
from gaminghub.services import game_service


GAME_SKILL_MAP = {
    "memory-matrix": "Memory",
    "reflex-lab": "Reaction",
    "focus-shift": "Attention",
    "sequence-breaker": "Pattern Recognition",
    "code-breaker": "Logic",
    "dual-task": "Multitasking",
    "risk-reward": "Decision Making",
    "logic-grid": "Logic",
}

# Two games map to Logic, so this is 7, not len(GAME_SKILL_MAP). The
# landing page quotes it rather than hardcoding a number that silently
# goes stale the next time a game is added.
SKILLS = sorted(set(GAME_SKILL_MAP.values()))


def get_overview(user):
    """
    One aggregate query for the headline stat row. Level/XP/Coins/Streak/
    Games Played/Win Rate come from the User row directly (already
    maintained by reward_service, no need to recompute); everything else
    needs an aggregate over GameResult.
    """

    agg = db.session.query(
        func.avg(GameResult.score),
        func.max(GameResult.score),
        func.avg(GameResult.accuracy),
        func.avg(GameResult.reaction_time)
    ).filter(GameResult.user_id == user.id).first()

    avg_score, best_score, avg_accuracy, avg_reaction_time = agg

    return {
        "level": user.level,
        "xp": user.xp,
        "coins": user.coins,
        "streak": user.daily_streak,
        "games_played": user.games_played,
        "win_rate": round(100 * user.wins / user.games_played) if user.games_played else None,
        "avg_score": round(avg_score) if avg_score is not None else None,
        "best_score": best_score,
        "avg_accuracy": round(avg_accuracy * 100) if avg_accuracy is not None else None,
        "avg_reaction_time": round(avg_reaction_time) if avg_reaction_time is not None else None
    }


def get_activity_over_time(user, days=14):
    """Games played and XP earned per day, for the last `days` days."""

    since = datetime.utcnow() - timedelta(days=days - 1)
    since_day_start = datetime(since.year, since.month, since.day)

    rows = db.session.query(
        GameResult.created_at,
        GameResult.xp_earned
    ).filter(
        GameResult.user_id == user.id,
        GameResult.created_at >= since_day_start
    ).all()

    games_by_day = defaultdict(int)
    xp_by_day = defaultdict(int)

    for created_at, xp_earned in rows:
        day = created_at.date().isoformat()
        games_by_day[day] += 1
        xp_by_day[day] += xp_earned or 0

    labels = [(since_day_start + timedelta(days=i)).date().isoformat() for i in range(days)]

    return {
        "labels": labels,
        "games_played": [games_by_day.get(d, 0) for d in labels],
        "xp_earned": [xp_by_day.get(d, 0) for d in labels]
    }


def get_per_game_breakdown(user):
    """Per-game stats table: plays, win rate, best/avg score, avg accuracy, avg reaction time."""

    rows = db.session.query(
        Game.name, Game.icon, Game.slug,
        GameResult.result, GameResult.score, GameResult.accuracy, GameResult.reaction_time
    ).join(
        GameResult, GameResult.game_id == Game.id
    ).filter(
        GameResult.user_id == user.id
    ).all()

    by_game = defaultdict(lambda: {"plays": 0, "wins": 0, "scores": [], "accuracies": [], "reaction_times": []})

    for name, icon, slug, result, score, accuracy, reaction_time in rows:
        d = by_game[(name, icon, slug)]
        d["plays"] += 1
        if result == "win":
            d["wins"] += 1
        d["scores"].append(score or 0)
        if accuracy is not None:
            d["accuracies"].append(accuracy)
        if reaction_time is not None:
            d["reaction_times"].append(reaction_time)

    breakdown = []

    for (name, icon, slug), d in by_game.items():
        breakdown.append({
            "name": name,
            "icon": icon,
            "slug": slug,
            "url": game_service.get_play_url(slug),
            "plays": d["plays"],
            "win_rate": round(100 * d["wins"] / d["plays"]),
            "best_score": max(d["scores"]),
            "avg_score": round(sum(d["scores"]) / len(d["scores"])),
            "avg_accuracy": round(100 * sum(d["accuracies"]) / len(d["accuracies"])) if d["accuracies"] else None,
            "avg_reaction_time": round(sum(d["reaction_times"]) / len(d["reaction_times"])) if d["reaction_times"] else None
        })

    breakdown.sort(key=lambda x: x["plays"], reverse=True)

    return breakdown


def get_skill_profile(user):
    """
    Win rate per skill category, derived from actual GameResult rows for
    the games mapped to each skill. Only includes skills the user has
    played at least once -- a skill nobody has data for is omitted
    rather than shown as 0%, which would misrepresent "no data" as
    "poor performance". This is a game-performance profile, not a
    psychological or clinical assessment.
    """

    rows = db.session.query(
        Game.slug, GameResult.result
    ).join(
        GameResult, GameResult.game_id == Game.id
    ).filter(
        GameResult.user_id == user.id
    ).all()

    plays = defaultdict(int)
    wins = defaultdict(int)

    for slug, result in rows:
        skill = GAME_SKILL_MAP.get(slug)
        if not skill:
            continue
        plays[skill] += 1
        if result == "win":
            wins[skill] += 1

    profile = []

    for skill in SKILLS:
        if plays[skill] >= 1:
            profile.append({
                "skill": skill,
                "score": round(100 * wins[skill] / plays[skill]),
                "plays": plays[skill]
            })

    return profile


def get_radar_profile(user=None):
    """
    Win rate for every skill in SKILLS, including the ones with no plays.

    get_skill_profile() above deliberately drops unplayed skills so a
    bar chart never renders "no data" as a 0% bar. A radar can't do
    that -- drop an axis and the polygon changes shape, so a beginner
    would appear to have a differently-shaped mind rather than less
    data. This variant keeps every axis and marks the empty ones with
    plays == 0, leaving it to the chart to dim them and to the caption
    to say what that means.

    user=None aggregates across all players: the platform average, used
    for logged-out visitors and as the comparison ring for logged-in
    ones.
    """

    query = db.session.query(Game.slug, GameResult.result).join(
        GameResult, GameResult.game_id == Game.id
    )

    if user is not None:
        query = query.filter(GameResult.user_id == user.id)

    plays = defaultdict(int)
    wins = defaultdict(int)

    for slug, result in query.all():
        skill = GAME_SKILL_MAP.get(slug)
        if not skill:
            continue
        plays[skill] += 1
        if result == "win":
            wins[skill] += 1

    return [
        {
            "skill": skill,
            "score": round(100 * wins[skill] / plays[skill]) if plays[skill] else 0,
            "plays": plays[skill],
        }
        for skill in SKILLS
    ]


def get_recommendations(user, limit=3):
    """
    Rule-based only: unplayed Brain Lab games first (discovery), then
    played games with the lowest win rate among those with enough
    plays to be meaningful. Never claims to be AI-driven -- it isn't.
    """

    brain_lab_games = Game.query.filter_by(category="brain-lab", is_active=True).all()

    rows = db.session.query(GameResult.game_id, GameResult.result).filter_by(user_id=user.id).all()

    plays = defaultdict(int)
    wins = defaultdict(int)

    for game_id, result in rows:
        plays[game_id] += 1
        if result == "win":
            wins[game_id] += 1

    recommendations = []

    for g in brain_lab_games:
        if len(recommendations) >= limit:
            break
        if plays[g.id] == 0:
            recommendations.append({
                "game": g,
                "reason": "You haven't tried this one yet.",
                "url": game_service.get_play_url(g.slug)
            })

    if len(recommendations) < limit:
        candidates = [g for g in brain_lab_games if plays[g.id] >= 2]
        candidates.sort(key=lambda g: wins[g.id] / plays[g.id])

        for g in candidates:
            if len(recommendations) >= limit:
                break
            win_rate = round(100 * wins[g.id] / plays[g.id])
            recommendations.append({
                "game": g,
                "reason": f"Your win rate here is {win_rate}% -- a bit more practice could help.",
                "url": game_service.get_play_url(g.slug)
            })

    return recommendations
