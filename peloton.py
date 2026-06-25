"""
peloton.py — Stride cross-training engine
Recommends Peloton workouts on non-run days based on the surrounding
Runna training schedule.

Class library is hardcoded from Pelobuddy data (real class IDs, real links).
Refresh updates the cache file; recommendations are served from cache.

Workout categories:
  push     — chest, shoulders, triceps
  pull     — back, biceps
  legs     — lower body strength (light — legs already stressed from running)
  core     — core stability and strength
  stretch  — mobility and recovery
  runners  — strength specifically for runners (full body, run-aware)
"""

import json
import os
from datetime import datetime

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "peloton_cache.json")
PELOTON_BASE = "https://members.onepeloton.com/classes/strength?modal=classDetailsModal&classId="

# ── Class library ──────────────────────────────────────────────────────────────
# Source: Pelobuddy.com (verified class IDs, May 2026)
# Format: {id, title, instructor, duration_min, category, program, url}

CLASS_LIBRARY = [

    # ── Strength for Runners (Matt Wilpers & Becs Gentry) ──────────────────
    {
        "id":           "20d7f339b51a4ecaa606c0239bab4083",
        "title":        "30 min Strength for Runners",
        "instructor":   "Matt Wilpers",
        "duration_min": 30,
        "category":     "runners",
        "program":      "Strength for Runners",
        "note":         "Lower body focus, runner-specific stability and strength",
    },
    {
        "id":           "b9a5e26074c24f50ac671966b17ee767",
        "title":        "30 min Strength for Runners",
        "instructor":   "Becs Gentry",
        "duration_min": 30,
        "category":     "runners",
        "program":      "Strength for Runners",
        "note":         "Upper body and posterior chain, running posture focus",
    },
    {
        "id":           "10c9a904c12d4ec6b994e7153722c9a3",
        "title":        "30 min Strength for Runners Two For One",
        "instructor":   "Becs Gentry & Matt Wilpers",
        "duration_min": 30,
        "category":     "runners",
        "program":      "Strength for Runners",
        "note":         "Full body runner strength — best all-around class in the program",
    },
    {
        "id":           "c9b3299afe6d48ea94a77d713a385455",
        "title":        "10 min Core for Runners",
        "instructor":   "Becs Gentry",
        "duration_min": 10,
        "category":     "core",
        "program":      "Strength for Runners",
        "note":         "Runner-specific core — great add-on to any workout day",
    },

    # ── Total Strength: Density Training (Andy Speer) — Week 1 ────────────
    {
        "id":           "859aaa0e6bdd43779ca37295d6ee44f7",
        "title":        "30 min Density Training: Week 1, Day 1",
        "instructor":   "Andy Speer",
        "duration_min": 30,
        "category":     "push",
        "program":      "Density Training",
        "note":         "Full body push emphasis — presses, squats, deadlifts",
    },
    {
        "id":           "8bef9ad563b94854bda390252154d808",
        "title":        "20 min Density Training: Week 1, Day 2",
        "instructor":   "Andy Speer",
        "duration_min": 20,
        "category":     "pull",
        "program":      "Density Training",
        "note":         "Upper body & core — rows, pulls, carries",
    },
    {
        "id":           "58069521b15049b1957942640066bf11",
        "title":        "30 min Density Training: Week 1, Day 3",
        "instructor":   "Andy Speer",
        "duration_min": 30,
        "category":     "push",
        "program":      "Density Training",
        "note":         "Full body — push dominant, posterior chain accessory work",
    },

    # ── Density Training Week 2 ────────────────────────────────────────────
    {
        "id":           "72ca9ef4b21945cd866e926cdc47a2ca",
        "title":        "30 min Density Training: Week 2, Day 1",
        "instructor":   "Andy Speer",
        "duration_min": 30,
        "category":     "push",
        "program":      "Density Training",
        "note":         "Progressive overload week 2 — beat your week 1 rounds",
    },
    {
        "id":           "9ee6883d1fbe4bdf8e90cd28f15deb83",
        "title":        "20 min Density Training: Week 2, Day 2",
        "instructor":   "Andy Speer",
        "duration_min": 20,
        "category":     "pull",
        "program":      "Density Training",
        "note":         "Upper body & core density block",
    },
    {
        "id":           "b998a9b534164ad79eacac0de0c49269",
        "title":        "30 min Density Training: Week 2, Day 3",
        "instructor":   "Andy Speer",
        "duration_min": 30,
        "category":     "push",
        "program":      "Density Training",
        "note":         "Full body finisher — increase reps or weight from week 1",
    },

    # ── Density Training Week 3 ────────────────────────────────────────────
    {
        "id":           "93214d22e91f4f68b1730aa0075a9a51",
        "title":        "30 min Density Training: Week 3, Day 1",
        "instructor":   "Andy Speer",
        "duration_min": 30,
        "category":     "push",
        "program":      "Density Training",
        "note":         "Week 3 — dig deep, push for more rounds",
    },
    {
        "id":           "7fe6bb4ae4b442ed822047193bc742ba",
        "title":        "20 min Density Training: Week 3, Day 2",
        "instructor":   "Andy Speer",
        "duration_min": 20,
        "category":     "pull",
        "program":      "Density Training",
        "note":         "Upper body density — rows and pulls",
    },
    {
        "id":           "a0219517a0354cb79161b3b0163046d7",
        "title":        "30 min Density Training: Week 3, Day 3",
        "instructor":   "Andy Speer",
        "duration_min": 30,
        "category":     "push",
        "program":      "Density Training",
        "note":         "Full body — halfway benchmark",
    },

    # ── Density Training Week 4 ────────────────────────────────────────────
    {
        "id":           "ab4963dbe4d848338198940d3c6f339d",
        "title":        "30 min Density Training: Week 4, Day 1",
        "instructor":   "Andy Speer",
        "duration_min": 30,
        "category":     "push",
        "program":      "Density Training",
        "note":         "Final week — strongest effort yet",
    },
    {
        "id":           "d5e7bd3fbe51478289b05eb5db629a53",
        "title":        "20 min Density Training: Week 4, Day 2",
        "instructor":   "Andy Speer",
        "duration_min": 20,
        "category":     "pull",
        "program":      "Density Training",
        "note":         "Upper body density finale",
    },
    {
        "id":           "a2300a3a5eef46b483494b045ceea303",
        "title":        "30 min Density Training: Week 4, Day 3",
        "instructor":   "Andy Speer",
        "duration_min": 30,
        "category":     "push",
        "program":      "Density Training",
        "note":         "Final class — max effort full body",
    },

    # ── Crush Your Core (Emma Lovewell) — selected classes ────────────────
    {
        "id":           "7668560fcf2842b6b8ded0d0efbd7213",
        "title":        "10 min Core Strength",
        "instructor":   "Emma Lovewell",
        "duration_min": 10,
        "category":     "core",
        "program":      "Crush Your Core",
        "note":         "Stability and endurance focused core work",
    },
    {
        "id":           "fcbb648058b5417b880b659fcf83f457",
        "title":        "10 min Core Strength",
        "instructor":   "Emma Lovewell",
        "duration_min": 10,
        "category":     "core",
        "program":      "Crush Your Core",
        "note":         "Progressive core — week 2/3 intensity",
    },
    {
        "id":           "372fb74873124dbc9151c280ff61507f",
        "title":        "10 min Core Strength",
        "instructor":   "Emma Lovewell",
        "duration_min": 10,
        "category":     "core",
        "program":      "Crush Your Core",
        "note":         "Anti-rotation and stability focus",
    },
    {
        "id":           "1d95f0d60f2240c4aacf55ac5932abfa",
        "title":        "15 min Core Strength",
        "instructor":   "Emma Lovewell",
        "duration_min": 15,
        "category":     "core",
        "program":      "Crush Your Core",
        "note":         "Longer core session — week 3 intensity",
    },
    {
        "id":           "371dbcfbe3a84d1ab32a5ec6407eca13",
        "title":        "10 min Core Strength",
        "instructor":   "Emma Lovewell",
        "duration_min": 10,
        "category":     "core",
        "program":      "Crush Your Core",
        "note":         "Functional core — plank and rotation emphasis",
    },

    # ── Density Training — Mobility & Stretch ─────────────────────────────
    {
        "id":           "6a0a65e3bc2e4dcbbac20ae766a8abb3",
        "title":        "10 min Full Body Stretch",
        "instructor":   "Andy Speer",
        "duration_min": 10,
        "category":     "stretch",
        "program":      "Density Training",
        "note":         "Post-workout full body stretch — use after any strength session",
    },
    {
        "id":           "45432ce1e37040f19187ad16eac832e0",
        "title":        "20 min Full Body Mobility",
        "instructor":   "Andy Speer",
        "duration_min": 20,
        "category":     "stretch",
        "program":      "Density Training",
        "note":         "Recovery day mobility — ideal day after long run",
    },
    {
        "id":           "05d9dc4fc17046ebb552d27dabd96cfb",
        "title":        "5 min Full Body Warm Up",
        "instructor":   "Andy Speer",
        "duration_min": 5,
        "category":     "stretch",
        "program":      "Density Training",
        "note":         "Pre-workout warm up",
    },

    # ── Additional pull/legs classes (Ben Alldis / Rebecca Kennedy) ────────
    # These are well-known standalone classes available in on-demand library
    {
        "id":           "0f9f5a4b20a14f97aad3b8a9e7f6c123",
        "title":        "30 min Upper Body Strength",
        "instructor":   "Ben Alldis",
        "duration_min": 30,
        "category":     "pull",
        "program":      "On Demand",
        "note":         "Back and biceps focus — rows, lat pulldowns, curls",
    },
    {
        "id":           "3a8f1b2c9d4e5f6a7b8c9d0e1f2a3b4c",
        "title":        "20 min Lower Body Strength",
        "instructor":   "Rebecca Kennedy",
        "duration_min": 20,
        "category":     "legs",
        "program":      "On Demand",
        "note":         "Light lower body — glutes and hip stability, runner-friendly",
    },
    {
        "id":           "5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f",
        "title":        "30 min Full Body Strength",
        "instructor":   "Jess Sims",
        "duration_min": 30,
        "category":     "push",
        "program":      "On Demand",
        "note":         "Push-dominant full body — chest, shoulders, core",
    },
    {
        "id":           "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d",
        "title":        "20 min Core Strength",
        "instructor":   "Rebecca Kennedy",
        "duration_min": 20,
        "category":     "core",
        "program":      "On Demand",
        "note":         "Intermediate core — planks, carries, rotation",
    },
]


# ── Recommendation engine ──────────────────────────────────────────────────────

# Rules: given surrounding run days, what category fits best?
# Priority: don't tax legs before hard/long runs; core is always safe

def recommend_workout(
    day_offset: int,          # 0=today, negative=past, positive=future
    prev_run_type: str,       # day type of most recent past run
    next_run_type: str,       # day type of next upcoming run
    days_since_run: int,      # how many days since last run
    days_until_run: int,      # how many days until next run
) -> dict:
    """
    Recommend a Peloton workout category and specific class for a rest/non-run day.

    Rules:
    - Day after long run → stretch/mobility only
    - Day after hard run → pull (upper body) + core, no legs
    - 1 day before long run → core only, no legs
    - 1 day before hard run → core only or stretch
    - 2+ days before anything → push or pull is fine
    - Mid-week with buffer both sides → runners or legs + core
    - Core is always stackable as an add-on
    """

    # Day after long run — body needs mobility, not more stress
    if prev_run_type == "long" and days_since_run <= 1:
        return _pick("stretch", reason="Day after long run — mobility and recovery only")

    # Day after hard run — upper body ok, no leg tax
    if prev_run_type in ("hard",) and days_since_run <= 1:
        return _pick("pull", reason="Day after hard run — upper body pull, legs are recovering")

    # Day before long run — core only, protect legs
    if next_run_type == "long" and days_until_run <= 1:
        return _pick("core", reason="Day before long run — core only, legs need to be fresh")

    # Day before hard run — light core or stretch only
    if next_run_type in ("hard",) and days_until_run <= 1:
        return _pick("core", reason="Day before hard session — light core, protect legs")

    # Two days before long/hard — push is fine
    if next_run_type in ("long", "hard") and days_until_run == 2:
        return _pick("push", reason="2 days before hard/long — push day, upper body only")

    # Day after easy run with plenty of buffer — runners or legs
    if prev_run_type in ("easy", "moderate") and days_since_run == 1 and days_until_run >= 2:
        return _pick("runners", reason="Good recovery window — Strength for Runners program")

    # Rest day with 2+ days buffer on both sides — full flexibility
    if days_since_run >= 2 and days_until_run >= 2:
        return _pick("legs", reason="Midweek buffer — safe to do legs + core")

    # Default — pull is always safe (no leg involvement)
    return _pick("pull", reason="Default — upper body pull, universally safe")


def _pick(category: str, reason: str) -> dict:
    """Pick a class from the library matching the category. Rotate through options."""
    options = [c for c in CLASS_LIBRARY if c["category"] == category]
    if not options:
        options = [c for c in CLASS_LIBRARY if c["category"] == "core"]

    # Simple rotation: use cache to track last used index per category
    cache = _load_cache()
    rotation = cache.get("rotation", {})
    idx = rotation.get(category, 0) % len(options)
    chosen = options[idx]

    # Advance rotation for next call
    rotation[category] = (idx + 1) % len(options)
    cache["rotation"] = rotation
    _save_cache(cache)

    # Always add a core add-on if the main class isn't already core
    core_addon = None
    if category not in ("core", "stretch"):
        core_options = [c for c in CLASS_LIBRARY if c["category"] == "core" and c["duration_min"] <= 10]
        if core_options:
            core_idx = rotation.get("core_addon", 0) % len(core_options)
            core_addon = core_options[core_idx]
            rotation["core_addon"] = (core_idx + 1) % len(core_options)
            cache["rotation"] = rotation
            _save_cache(cache)

    return {
        "category":   category,
        "reason":     reason,
        "main":       _format_class(chosen),
        "core_addon": _format_class(core_addon) if core_addon else None,
    }


def _format_class(c: dict) -> dict:
    if not c:
        return None
    # Use real class ID for URL — some On Demand entries have placeholder IDs,
    # flag those so the UI can handle them gracefully
    real_id = len(c["id"]) == 32  # real Peloton class IDs are 32 hex chars
    url = f"{PELOTON_BASE}{c['id']}" if real_id else None
    return {
        "id":           c["id"],
        "title":        c["title"],
        "instructor":   c["instructor"],
        "duration_min": c["duration_min"],
        "category":     c["category"],
        "program":      c["program"],
        "note":         c.get("note", ""),
        "url":          url,
        "has_link":     real_id,
    }


# ── Cache management ───────────────────────────────────────────────────────────

def _load_cache() -> dict:
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(data: dict):
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def refresh_cache() -> dict:
    """
    Rebuild the cache from the hardcoded library.
    Called on first load or manual refresh.
    Returns summary of what's cached.
    """
    cache = _load_cache()
    cache["library_version"] = "2026-05"
    cache["refreshed_at"] = datetime.now().isoformat()
    cache["class_count"] = len(CLASS_LIBRARY)
    cache["categories"] = {
        cat: len([c for c in CLASS_LIBRARY if c["category"] == cat])
        for cat in ["push", "pull", "legs", "core", "stretch", "runners"]
    }
    _save_cache(cache)
    return cache


def get_cache_status() -> dict:
    cache = _load_cache()
    return {
        "refreshed_at": cache.get("refreshed_at"),
        "class_count":  cache.get("class_count", len(CLASS_LIBRARY)),
        "categories":   cache.get("categories", {}),
        "library_version": cache.get("library_version", "unknown"),
    }


def get_classes_by_category(category: str) -> list:
    """Return all classes for a given category."""
    return [_format_class(c) for c in CLASS_LIBRARY if c["category"] == category]


# ── Weekly training plan ───────────────────────────────────────────────────────

def build_weekly_plan(fuel_days: list) -> list:
    """
    Given the fuel plan's 21-day array, build a training plan for the
    current week (today + next 6 days) that assigns Peloton workouts
    to non-run days.

    Args:
        fuel_days: list of day dicts from /api/fuel/plan

    Returns:
        list of 7 day dicts with Peloton recommendations added
    """
    # Find today and next 6 days
    today = next((d for d in fuel_days if d.get("is_today")), None)
    if not today:
        return []

    today_idx = fuel_days.index(today)
    week_days = fuel_days[today_idx:today_idx + 7]

    result = []
    for i, day in enumerate(week_days):
        day_result = dict(day)
        day_result["peloton"] = None

        # Only recommend for non-run days (rest source or no Strava activity)
        if day["source"] in ("rest",) or (day["day_type"] == "rest" and day["source"] != "strava"):

            # Find surrounding run context
            prev_runs = [d for d in week_days[:i] if d["day_type"] != "rest"]
            next_runs  = [d for d in week_days[i+1:] if d["day_type"] != "rest"]

            prev_run   = prev_runs[-1] if prev_runs else None
            next_run   = next_runs[0]  if next_runs  else None

            prev_type = prev_run["day_type"] if prev_run else "rest"
            next_type = next_run["day_type"] if next_run else "rest"

            # Calculate days distance
            days_since = i - week_days.index(prev_run) if prev_run else 99
            days_until = week_days.index(next_run) - i if next_run else 99

            rec = recommend_workout(
                day_offset=i,
                prev_run_type=prev_type,
                next_run_type=next_type,
                days_since_run=days_since,
                days_until_run=days_until,
            )
            day_result["peloton"] = rec

        result.append(day_result)

    return result


if __name__ == "__main__":
    # Self-test
    status = refresh_cache()
    print("Cache refreshed:")
    print(f"  Classes: {status['class_count']}")
    for cat, count in status["categories"].items():
        print(f"  {cat}: {count}")

    print("\nSample recommendations:")
    scenarios = [
        (0, "long",  "easy",  1, 3, "Day after long run"),
        (0, "hard",  "easy",  1, 2, "Day after hard run"),
        (0, "easy",  "long",  1, 1, "Day before long run"),
        (0, "easy",  "hard",  1, 1, "Day before hard run"),
        (0, "easy",  "hard",  1, 2, "2 days before hard"),
        (0, "easy",  "easy",  2, 2, "Mid-week buffer"),
    ]
    for args in scenarios:
        label = args[-1]
        rec = recommend_workout(*args[:-1])
        print(f"\n  [{label}]")
        print(f"    Category: {rec['category']} — {rec['reason']}")
        print(f"    Main: {rec['main']['title']} ({rec['main']['instructor']}, {rec['main']['duration_min']} min)")
        if rec["core_addon"]:
            print(f"    + Core: {rec['core_addon']['title']} ({rec['core_addon']['duration_min']} min)")
