"""
FocusFlow Gamification, Leveling, Rewards and Achievement Engine.
Provides mathematical formulas, progression logic, streak calculation,
anti-exploit validation, and persistent achievement evaluation.
"""

from datetime import datetime, timezone, timedelta
import sqlite3

# XP values for genuine productivity activities
XP_PER_TASK = 10
XP_DAILY_STREAK = 15
XP_WEEKLY_GOAL = 50
WEEKLY_FOCUS_MINUTES_GOAL = 120  # 2 hours per week to earn weekly goal bonus

# Level progression titles
LEVEL_TITLES = {
    1: "Beginner",
    2: "Getting Started",
    3: "Focus Explorer",
    4: "Focus Apprentice",
    5: "Productivity Enthusiast",
    6: "Deep Work Initiate",
    7: "Flow Practitioner",
    8: "Routine Architect",
    9: "Discipline Adept",
    10: "Focus Master",
    15: "Mindful Strategist",
    20: "Productivity Champion",
    25: "Grand Architect",
    30: "Elite Performer",
}

# Rank tiers based on total XP
RANKS = [
    {
        "name": "Bronze",
        "min_xp": 0,
        "max_xp": 499,
        "color": "#c88346",
        "badge": "bronze",
        "description": "Foundation of Focus",
    },
    {
        "name": "Silver",
        "min_xp": 500,
        "max_xp": 1499,
        "color": "#9aa4c2",
        "badge": "silver",
        "description": "Consistent Striver",
    },
    {
        "name": "Gold",
        "min_xp": 1500,
        "max_xp": 3499,
        "color": "#f5c842",
        "badge": "gold",
        "description": "Deep Worker",
    },
    {
        "name": "Platinum",
        "min_xp": 3500,
        "max_xp": 6999,
        "color": "#4ecdc4",
        "badge": "platinum",
        "description": "Master of Flow",
    },
    {
        "name": "Diamond",
        "min_xp": 7000,
        "max_xp": 11999,
        "color": "#8b6eff",
        "badge": "diamond",
        "description": "Relentless Discipline",
    },
    {
        "name": "Master",
        "min_xp": 12000,
        "max_xp": float("inf"),
        "color": "#ff4d88",
        "badge": "master",
        "description": "Zenith of Productivity",
    },
]

# Official Achievement catalog
ACHIEVEMENTS_CATALOG = [
    {
        "id": "first_focus",
        "name": "First Focus",
        "category": "Focus",
        "description": "Complete your first focus session.",
        "requirement": "1 completed focus session",
        "icon": "target",
        "xp_reward": 25,
        "target": 1,
    },
    {
        "id": "deep_worker",
        "name": "Deep Worker",
        "category": "Focus",
        "description": "Complete 10 focus sessions.",
        "requirement": "10 completed focus sessions",
        "icon": "brain",
        "xp_reward": 50,
        "target": 10,
    },
    {
        "id": "focus_champion",
        "name": "Focus Champion",
        "category": "Focus",
        "description": "Accumulate 10 hours (600 minutes) of focused work.",
        "requirement": "600 minutes of total focus time",
        "icon": "trophy",
        "xp_reward": 100,
        "target": 600,
    },
    {
        "id": "consistency_king",
        "name": "Consistency King",
        "category": "Consistency",
        "description": "Maintain a 7-day productivity streak.",
        "requirement": "7-day productivity streak",
        "icon": "crown",
        "xp_reward": 75,
        "target": 7,
    },
    {
        "id": "task_master",
        "name": "Task Master",
        "category": "Tasks",
        "description": "Complete 50 tasks across your workspace.",
        "requirement": "50 completed tasks",
        "icon": "checkCircle",
        "xp_reward": 100,
        "target": 50,
    },
    {
        "id": "early_bird",
        "name": "Early Bird",
        "category": "Discipline",
        "description": "Complete a focus session before 8:00 AM.",
        "requirement": "Session completed before 8:00 AM",
        "icon": "sunrise",
        "xp_reward": 30,
        "target": 1,
    },
    {
        "id": "marathon_worker",
        "name": "Marathon Worker",
        "category": "Focus",
        "description": "Complete an extended focus session of 50 minutes or longer.",
        "requirement": "Single session >= 50 minutes",
        "icon": "flame",
        "xp_reward": 40,
        "target": 1,
    },
    {
        "id": "first_task",
        "name": "First Step",
        "category": "Tasks",
        "description": "Complete your very first task.",
        "requirement": "1 completed task",
        "icon": "check",
        "xp_reward": 15,
        "target": 1,
    },
    {
        "id": "high_priority_striker",
        "name": "Priority Striker",
        "category": "Tasks",
        "description": "Complete 5 high-priority tasks.",
        "requirement": "5 high-priority tasks completed",
        "icon": "bolt",
        "xp_reward": 35,
        "target": 5,
    },
    {
        "id": "night_owl",
        "name": "Night Owl",
        "category": "Discipline",
        "description": "Complete a focus session after 10:00 PM.",
        "requirement": "Session completed after 10:00 PM",
        "icon": "moon",
        "xp_reward": 30,
        "target": 1,
    },
    {
        "id": "streak_starter",
        "name": "Momentum Builder",
        "category": "Consistency",
        "description": "Maintain a 3-day productivity streak.",
        "requirement": "3-day productivity streak",
        "icon": "trendingUp",
        "xp_reward": 30,
        "target": 3,
    },
    {
        "id": "focus_master",
        "name": "Elite Scholar",
        "category": "Progression",
        "description": "Reach Level 10 (Focus Master).",
        "requirement": "Reach Level 10",
        "icon": "award",
        "xp_reward": 150,
        "target": 10,
    },
]

ACHIEVEMENTS_BY_ID = {a["id"]: a for a in ACHIEVEMENTS_CATALOG}


def total_xp_for_level(level: int) -> int:
    """Returns the cumulative XP required to reach the start of `level`."""
    if level <= 1:
        return 0
    # Formula: 25 * (L - 1) * (L + 2)
    # L=1: 0, L=2: 100, L=3: 250, L=4: 450, L=5: 700, L=10: 2700
    return 25 * (level - 1) * (level + 2)


def xp_required_for_next_level(level: int) -> int:
    """XP needed to advance from `level` to `level + 1`."""
    return 50 + 50 * level


def calculate_level(total_xp: int):
    """
    Computes level, title, XP within current level, XP needed for next level,
    and progress percentage.
    """
    total_xp = max(0, int(total_xp))
    level = 1
    while total_xp >= total_xp_for_level(level + 1):
        level += 1

    current_base = total_xp_for_level(level)
    next_base = total_xp_for_level(level + 1)
    xp_in_level = total_xp - current_base
    xp_needed = next_base - current_base
    progress_pct = min(100, max(0, round((xp_in_level / xp_needed) * 100)))

    # Title lookup: highest milestone <= level
    title = "Beginner"
    for lvl in sorted(LEVEL_TITLES.keys()):
        if level >= lvl:
            title = LEVEL_TITLES[lvl]
        else:
            break

    return {
        "level": level,
        "title": title,
        "current_level_xp": xp_in_level,
        "next_level_xp": xp_needed,
        "total_xp": total_xp,
        "progress_percent": progress_pct,
    }


def calculate_rank(total_xp: int):
    """Returns rank tier info based on total XP."""
    total_xp = max(0, int(total_xp))
    for r in reversed(RANKS):
        if total_xp >= r["min_xp"]:
            return {
                "name": r["name"],
                "color": r["color"],
                "badge": r["badge"],
                "description": r["description"],
                "min_xp": r["min_xp"],
                "max_xp": r["max_xp"] if r["max_xp"] != float("inf") else None,
            }
    return {
        "name": RANKS[0]["name"],
        "color": RANKS[0]["color"],
        "badge": RANKS[0]["badge"],
        "description": RANKS[0]["description"],
        "min_xp": 0,
        "max_xp": RANKS[0]["max_xp"],
    }


def calculate_session_xp(duration_minutes: int) -> int:
    """
    Calculates XP for a successfully completed focus session.
    - 25 minutes = 25 XP
    - 50 minutes = 50 XP
    - 1 XP per minute for genuine sessions (>= 5 minutes).
    - Under 5 minutes: 0 XP (anti-exploit).
    - Capped at 120 XP.
    """
    try:
        mins = int(duration_minutes)
    except (TypeError, ValueError):
        mins = 0

    if mins < 5:
        return 0
    return min(120, mins)


def get_or_init_progression(db: sqlite3.Connection, user_id: int):
    """
    Retrieves or initializes a user's progression row in the database.
    If the user has historical sessions or tasks without XP, retroactively
    initializes their baseline progression and awards achievements.
    """
    row = db.execute(
        "SELECT * FROM user_progression WHERE user_id=?", (user_id,)
    ).fetchone()

    if row is None:
        now_iso = datetime.now(timezone.utc).isoformat()
        db.execute(
            """INSERT INTO user_progression(user_id, total_xp, current_level, rank_tier, current_streak, last_active_date, updated_at)
               VALUES(?, 0, 1, 'Bronze', 0, '', ?)""",
            (user_id, now_iso),
        )
        db.commit()

        # Retroactive baseline calculation for existing accounts
        _sync_historical_activity(db, user_id)

        row = db.execute(
            "SELECT * FROM user_progression WHERE user_id=?", (user_id,)
        ).fetchone()

    return dict(row)


def _sync_historical_activity(db: sqlite3.Connection, user_id: int):
    """Awards XP and syncs historical tasks and sessions for existing users."""
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Historical sessions
    sessions = db.execute(
        "SELECT id, duration_minutes, completed_at, xp_awarded FROM sessions WHERE user_id=? ORDER BY id ASC",
        (user_id,),
    ).fetchall()

    for s in sessions:
        if not s["xp_awarded"]:
            xp = calculate_session_xp(s["duration_minutes"])
            if xp > 0:
                try:
                    db.execute(
                        """INSERT INTO xp_transactions(user_id, amount, activity_type, reference_id, description, created_at)
                           VALUES(?, ?, 'session', ?, ?, ?)""",
                        (
                            user_id,
                            xp,
                            f"session:{s['id']}",
                            f"{s['duration_minutes']}-min focus session",
                            s["completed_at"] or now_iso,
                        ),
                    )
                except sqlite3.IntegrityError:
                    pass
            db.execute("UPDATE sessions SET xp_awarded=1 WHERE id=?", (s["id"],))

    # 2. Historical completed tasks
    tasks = db.execute(
        "SELECT id, title, completed, xp_awarded, created_at FROM tasks WHERE user_id=? AND completed=1",
        (user_id,),
    ).fetchall()

    for t in tasks:
        if not t["xp_awarded"]:
            try:
                db.execute(
                    """INSERT INTO xp_transactions(user_id, amount, activity_type, reference_id, description, created_at)
                       VALUES(?, ?, 'task', ?, ?, ?)""",
                    (
                        user_id,
                        XP_PER_TASK,
                        f"task:{t['id']}",
                        f"Completed task: {t['title'][:40]}",
                        t["created_at"] or now_iso,
                    ),
                )
            except sqlite3.IntegrityError:
                pass
            db.execute("UPDATE tasks SET xp_awarded=1 WHERE id=?", (t["id"],))

    # Re-sum total XP from transactions
    total = (
        db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_transactions WHERE user_id=?",
            (user_id,),
        ).fetchone()[0]
        or 0
    )

    lvl_info = calculate_level(total)
    rank_info = calculate_rank(total)

    db.execute(
        """UPDATE user_progression
           SET total_xp=?, current_level=?, rank_tier=?, updated_at=?
           WHERE user_id=?""",
        (total, lvl_info["level"], rank_info["name"], now_iso, user_id),
    )
    db.commit()


def compute_current_streak(db: sqlite3.Connection, user_id: int) -> int:
    """
    Computes active daily streak based on distinct dates of completed sessions
    and completed tasks. A streak continues if there is activity today or yesterday.
    """
    # Fetch distinct dates of activity
    session_dates = db.execute(
        "SELECT substr(completed_at, 1, 10) as dt FROM sessions WHERE user_id=? AND completed_at IS NOT NULL AND completed_at != '' GROUP BY dt",
        (user_id,),
    ).fetchall()

    task_dates = db.execute(
        "SELECT substr(created_at, 1, 10) as dt FROM tasks WHERE user_id=? AND completed=1 AND created_at IS NOT NULL AND created_at != '' GROUP BY dt",
        (user_id,),
    ).fetchall()

    dates = {r["dt"] for r in session_dates if r["dt"]}.union(
        {r["dt"] for r in task_dates if r["dt"]}
    )

    if not dates:
        return 0

    today = datetime.now(timezone.utc).date()
    today_str = today.isoformat()
    yesterday_str = (today - timedelta(days=1)).isoformat()

    # Determine anchor date: if user active today, count backward from today;
    # if user active yesterday, count backward from yesterday.
    if today_str in dates:
        anchor = today
    elif yesterday_str in dates:
        anchor = today - timedelta(days=1)
    else:
        # Streak broken
        return 0

    streak = 0
    curr = anchor
    while curr.isoformat() in dates:
        streak += 1
        curr -= timedelta(days=1)

    return streak


def update_user_streak_and_award_bonus(db: sqlite3.Connection, user_id: int):
    """
    Updates the streak and awards the daily streak bonus XP once per calendar day.
    """
    streak = compute_current_streak(db, user_id)
    today_str = datetime.now(timezone.utc).date().isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    bonus_awarded = 0
    # Award daily streak bonus if streak >= 1 and not yet awarded today
    if streak >= 1:
        try:
            db.execute(
                """INSERT INTO xp_transactions(user_id, amount, activity_type, reference_id, description, created_at)
                   VALUES(?, ?, 'daily_streak', ?, ?, ?)""",
                (
                    user_id,
                    XP_DAILY_STREAK,
                    f"streak:{today_str}",
                    f"Daily productivity streak bonus ({streak} days)",
                    now_iso,
                ),
            )
            bonus_awarded = XP_DAILY_STREAK
        except sqlite3.IntegrityError:
            # Already awarded today
            pass

    # Update progression row
    db.execute(
        """UPDATE user_progression
           SET current_streak=?, last_active_date=?, updated_at=?
           WHERE user_id=?""",
        (streak, today_str, now_iso, user_id),
    )

    if bonus_awarded > 0:
        _recalculate_user_level_and_rank(db, user_id)

    return {"streak": streak, "bonus_xp": bonus_awarded}


def check_weekly_focus_goal_bonus(db: sqlite3.Connection, user_id: int):
    """
    Checks if user completed >= WEEKLY_FOCUS_MINUTES_GOAL in the current calendar week.
    Awards +50 XP bonus once per calendar week.
    """
    now = datetime.now(timezone.utc)
    # Start of current week (Monday)
    start_of_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_iso = start_of_week.isoformat()
    week_id = f"weekly:{now.year}-W{now.isocalendar()[1]}"

    row = db.execute(
        """SELECT COALESCE(SUM(duration_minutes), 0) FROM sessions
           WHERE user_id=? AND completed_at >= ?""",
        (user_id, start_iso),
    ).fetchone()

    minutes_this_week = row[0] or 0
    if minutes_this_week >= WEEKLY_FOCUS_MINUTES_GOAL:
        try:
            db.execute(
                """INSERT INTO xp_transactions(user_id, amount, activity_type, reference_id, description, created_at)
                   VALUES(?, ?, 'weekly_goal', ?, ?, ?)""",
                (
                    user_id,
                    XP_WEEKLY_GOAL,
                    week_id,
                    f"Weekly focus goal reached ({minutes_this_week}m / {WEEKLY_FOCUS_MINUTES_GOAL}m)",
                    now.isoformat(),
                ),
            )
            _recalculate_user_level_and_rank(db, user_id)
            return {"awarded": True, "xp": XP_WEEKLY_GOAL}
        except sqlite3.IntegrityError:
            # Already awarded for this week
            pass

    return {"awarded": False, "xp": 0}


def award_xp(
    db: sqlite3.Connection,
    user_id: int,
    amount: int,
    activity_type: str,
    reference_id: str,
    description: str,
):
    """
    Safely awards XP with duplicate-prevention via unique constraint.
    Updates total XP, checks for level up, and returns status.
    """
    if amount <= 0:
        return {"awarded": False, "amount": 0, "leveled_up": False}

    now_iso = datetime.now(timezone.utc).isoformat()
    prog_before = get_or_init_progression(db, user_id)
    level_before = prog_before["current_level"]

    try:
        db.execute(
            """INSERT INTO xp_transactions(user_id, amount, activity_type, reference_id, description, created_at)
               VALUES(?, ?, ?, ?, ?, ?)""",
            (user_id, amount, activity_type, reference_id, description, now_iso),
        )
    except sqlite3.IntegrityError:
        # Duplicate award prevented!
        return {"awarded": False, "amount": 0, "leveled_up": False, "duplicate": True}

    # Recalculate progression
    prog_after = _recalculate_user_level_and_rank(db, user_id)
    leveled_up = prog_after["current_level"] > level_before

    return {
        "awarded": True,
        "amount": amount,
        "leveled_up": leveled_up,
        "old_level": level_before,
        "new_level": prog_after["current_level"],
        "new_title": prog_after["level_title"],
        "total_xp": prog_after["total_xp"],
    }


def _recalculate_user_level_and_rank(db: sqlite3.Connection, user_id: int):
    """Recalculates user's total XP from ledger and updates progression record."""
    total = (
        db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_transactions WHERE user_id=?",
            (user_id,),
        ).fetchone()[0]
        or 0
    )

    lvl_info = calculate_level(total)
    rank_info = calculate_rank(total)
    now_iso = datetime.now(timezone.utc).isoformat()

    db.execute(
        """UPDATE user_progression
           SET total_xp=?, current_level=?, rank_tier=?, updated_at=?
           WHERE user_id=?""",
        (total, lvl_info["level"], rank_info["name"], now_iso, user_id),
    )
    db.commit()

    return {
        "total_xp": total,
        "current_level": lvl_info["level"],
        "level_title": lvl_info["title"],
        "rank_tier": rank_info["name"],
    }


def check_and_unlock_achievements(db: sqlite3.Connection, user_id: int):
    """
    Evaluates all achievements against user's actual database records.
    Awards any newly unlocked achievements and returns a list of newly unlocked ones.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # Gather user statistics
    sessions = db.execute(
        "SELECT id, duration_minutes, completed_at FROM sessions WHERE user_id=?",
        (user_id,),
    ).fetchall()

    tasks_completed = db.execute(
        "SELECT id, priority, created_at FROM tasks WHERE user_id=? AND completed=1",
        (user_id,),
    ).fetchall()

    prog = get_or_init_progression(db, user_id)
    streak = compute_current_streak(db, user_id)

    total_sessions_count = len(sessions)
    total_focus_minutes = sum(s["duration_minutes"] for s in sessions)
    completed_tasks_count = len(tasks_completed)
    high_priority_tasks_count = sum(
        1 for t in tasks_completed if str(t["priority"]).lower() == "high"
    )

    # Check session times
    has_early_bird = False
    has_night_owl = False
    has_marathon = False

    for s in sessions:
        if s["duration_minutes"] >= 50:
            has_marathon = True
        stamp = s["completed_at"]
        if stamp:
            try:
                # Format: YYYY-MM-DDTHH:MM:SS or similar
                hour = int(stamp[11:13]) if len(stamp) >= 13 else 12
                if hour < 8:
                    has_early_bird = True
                if hour >= 22 or hour < 4:
                    has_night_owl = True
            except (ValueError, IndexError):
                pass

    # Already unlocked
    unlocked_rows = db.execute(
        "SELECT achievement_id FROM user_achievements WHERE user_id=?", (user_id,)
    ).fetchall()
    already_unlocked = {r["achievement_id"] for r in unlocked_rows}

    newly_unlocked = []

    for a in ACHIEVEMENTS_CATALOG:
        aid = a["id"]
        if aid in already_unlocked:
            continue

        unlocked = False
        if aid == "first_focus" and total_sessions_count >= 1:
            unlocked = True
        elif aid == "deep_worker" and total_sessions_count >= 10:
            unlocked = True
        elif aid == "focus_champion" and total_focus_minutes >= 600:
            unlocked = True
        elif aid == "consistency_king" and streak >= 7:
            unlocked = True
        elif aid == "task_master" and completed_tasks_count >= 50:
            unlocked = True
        elif aid == "early_bird" and has_early_bird:
            unlocked = True
        elif aid == "marathon_worker" and has_marathon:
            unlocked = True
        elif aid == "first_task" and completed_tasks_count >= 1:
            unlocked = True
        elif aid == "high_priority_striker" and high_priority_tasks_count >= 5:
            unlocked = True
        elif aid == "night_owl" and has_night_owl:
            unlocked = True
        elif aid == "streak_starter" and streak >= 3:
            unlocked = True
        elif aid == "focus_master" and prog["current_level"] >= 10:
            unlocked = True

        if unlocked:
            try:
                db.execute(
                    """INSERT INTO user_achievements(user_id, achievement_id, unlocked_at)
                       VALUES(?, ?, ?)""",
                    (user_id, aid, now_iso),
                )
                db.commit()

                # Award achievement bonus XP
                if a["xp_reward"] > 0:
                    award_xp(
                        db,
                        user_id,
                        a["xp_reward"],
                        "achievement",
                        f"achievement:{aid}",
                        f"Unlocked achievement: {a['name']}",
                    )

                newly_unlocked.append(
                    {
                        "id": a["id"],
                        "name": a["name"],
                        "description": a["description"],
                        "icon": a["icon"],
                        "xp_reward": a["xp_reward"],
                        "unlocked_at": now_iso,
                    }
                )
            except sqlite3.IntegrityError:
                pass

    return newly_unlocked


def get_user_progression_summary(db: sqlite3.Connection, user_id: int):
    """
    Compiles the full progression, ranks, stats, weekly XP, achievements,
    and upcoming unlock for the user profile and dashboard.
    """
    prog = get_or_init_progression(db, user_id)
    total_xp = prog["total_xp"]
    lvl_info = calculate_level(total_xp)
    rank_info = calculate_rank(total_xp)
    streak = compute_current_streak(db, user_id)

    # Core stats
    session_stats = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(duration_minutes), 0) FROM sessions WHERE user_id=?",
        (user_id,),
    ).fetchone()
    total_sessions = session_stats[0] or 0
    total_focus_minutes = session_stats[1] or 0
    total_focus_hours = round(total_focus_minutes / 60, 1)

    completed_tasks = (
        db.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id=? AND completed=1", (user_id,)
        ).fetchone()[0]
        or 0
    )

    # Weekly XP calculation (last 7 days / current calendar week)
    now = datetime.now(timezone.utc)
    start_of_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    weekly_xp = (
        db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_transactions WHERE user_id=? AND created_at >= ?",
            (user_id, start_of_week.isoformat()),
        ).fetchone()[0]
        or 0
    )

    # Achievements list
    unlocked_map = {
        r["achievement_id"]: r["unlocked_at"]
        for r in db.execute(
            "SELECT achievement_id, unlocked_at FROM user_achievements WHERE user_id=?",
            (user_id,),
        ).fetchall()
    }

    achievements_list = []
    next_achievement = None
    min_remaining_ratio = float("inf")

    for a in ACHIEVEMENTS_CATALOG:
        is_unlocked = a["id"] in unlocked_map
        unlocked_date = unlocked_map.get(a["id"])

        # Progress calculation for locked achievements
        curr_progress = 0
        target = a.get("target", 1)
        if a["id"] in ("first_focus", "deep_worker"):
            curr_progress = min(target, total_sessions)
        elif a["id"] == "focus_champion":
            curr_progress = min(target, total_focus_minutes)
        elif a["id"] in ("consistency_king", "streak_starter"):
            curr_progress = min(target, streak)
        elif a["id"] in ("task_master", "first_task"):
            curr_progress = min(target, completed_tasks)
        elif a["id"] == "focus_master":
            curr_progress = min(target, lvl_info["level"])
        else:
            curr_progress = 1 if is_unlocked else 0

        ach_item = {
            "id": a["id"],
            "name": a["name"],
            "category": a["category"],
            "description": a["description"],
            "requirement": a["requirement"],
            "icon": a["icon"],
            "xp_reward": a["xp_reward"],
            "target": target,
            "current_progress": curr_progress,
            "unlocked": is_unlocked,
            "unlocked_at": unlocked_date,
        }
        achievements_list.append(ach_item)

        # Track nearest unlockable achievement for the dashboard widget
        if not is_unlocked and target > 0:
            ratio = (target - curr_progress) / target
            if ratio < min_remaining_ratio:
                min_remaining_ratio = ratio
                next_achievement = ach_item

    # Recent transactions
    tx_rows = db.execute(
        "SELECT id, amount, activity_type, description, created_at FROM xp_transactions WHERE user_id=? ORDER BY id DESC LIMIT 6",
        (user_id,),
    ).fetchall()

    return {
        "total_xp": total_xp,
        "current_level": lvl_info["level"],
        "level_title": lvl_info["title"],
        "rank_tier": rank_info["name"],
        "rank_badge": rank_info["badge"],
        "rank_color": rank_info["color"],
        "rank_description": rank_info["description"],
        "current_level_xp": lvl_info["current_level_xp"],
        "next_level_xp": lvl_info["next_level_xp"],
        "progress_percent": lvl_info["progress_percent"],
        "total_focus_hours": total_focus_hours,
        "total_focus_minutes": total_focus_minutes,
        "total_sessions": total_sessions,
        "completed_tasks": completed_tasks,
        "current_streak": streak,
        "weekly_xp": weekly_xp,
        "unlocked_achievements_count": len(unlocked_map),
        "total_achievements_count": len(ACHIEVEMENTS_CATALOG),
        "next_achievement": next_achievement,
        "achievements": achievements_list,
        "recent_activity": [dict(r) for r in tx_rows],
    }
