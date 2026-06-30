"""
fuel.py — Stride nutrition engine
Classifies training days and computes personalized macro targets.
Integrates with Strava (all activity types) and Runna via Google Calendar.

Macro philosophy (Weight Loss Target: 65-67kg):
  - Protein: 160-170g daily — non-negotiable foundation to protect muscle mass
  - Carbs: dynamic periodization — rest=130g, easy=200g, moderate=250g, hard=300g, long=350g
  - Fat: steady 60-75g (hormonal function and joint health)
  - Calories: ~1680 rest -> ~2750 long
"""

import re
import math

def _read_env(key, default=""):
    val = os.environ.get(key, "")
    if val: return val
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(here, ".env")) as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return default

EST_MAX_HR = float(_read_env("ATHLETE_ESTIM_MAX_HR", "198"))

DAY_TYPES = ["rest", "easy", "moderate", "hard", "long"]

DAY_TYPE_COLOR = {
    "rest":     "red",
    "easy":     "yellow",
    "moderate": "yellow",
    "hard":     "green",
    "long":     "green",
    # Peloton-adjusted rest days
    "rest_push":    "yellow",
    "rest_pull":    "yellow",
    "rest_legs":    "yellow",
    "rest_runners": "yellow",
    "rest_core":    "red",
    "rest_stretch": "red",
}

# Maps Peloton category to effective fuel day type
PELOTON_FUEL_MAP = {
    "push":    "easy",      # upper body push — similar load to easy run
    "pull":    "easy",      # upper body pull — similar load to easy run
    "legs":    "moderate",  # leg day — meaningful glycogen demand
    "runners": "easy",      # runner-specific strength — easy equivalent
    "core":    "rest",      # core only — minimal caloric impact
    "stretch": "rest",      # mobility — no additional fuel needed
}

# Fixed gram targets — not % of TDEE
MACRO_TARGETS = {
    "rest":     {"protein_g": 160, "carbs_g": 130, "fat_g": 60},  # ~1700 kcal
    "easy":     {"protein_g": 160, "carbs_g": 200, "fat_g": 65},  # ~2025 kcal
    "moderate": {"protein_g": 165, "carbs_g": 250, "fat_g": 70},  # ~2290 kcal
    "hard":     {"protein_g": 170, "carbs_g": 300, "fat_g": 75},  # ~2555 kcal
    "long":     {"protein_g": 170, "carbs_g": 350, "fat_g": 75},  # ~2755 kcal
}

ACTIVITY_MULTIPLIER = {
    "rest":     1.20,
    "easy":     1.35,
    "moderate": 1.50,
    "hard":     1.65,
    "long":     1.80,
}

EXTRA_BURN = {
    "rest":     0,
    "easy":     0,
    "moderate": 0,
    "hard":     0,
    "long":     0,
}

# Strava activity types that count as training
TRAINING_TYPES = {
    "Run", "VirtualRun", "TrailRun",
    "Ride", "VirtualRide", "EBikeRide",
    "Swim", "Rowing", "Kayaking", "Canoeing",
    "NordicSki", "BackcountrySki", "AlpineSki", "Snowboard",
    "Elliptical", "StairStepper",
    "WeightTraining", "Crossfit", "Workout",
    "HighIntensityIntervalTraining", "CircuitTraining",
    "Hike", "Walk", "Soccer", "Tennis", "Basketball",
    "Volleyball", "Golf", "MartialArts", "Yoga", "Pilates",
}

STRENGTH_TYPES = {
    "WeightTraining", "Crossfit", "Workout",
    "HighIntensityIntervalTraining", "CircuitTraining",
    "MartialArts",
}

LOW_INTENSITY_TYPES = {
    "Walk", "Yoga", "Pilates", "Golf",
}


def compute_bmr(weight_kg: float, height_cm: float, age: int) -> float:
    """Mifflin-St Jeor BMR for a male athlete. Fixed hardcoded values."""
    return (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5


def tdee_for_day(bmr: float, day_type: str) -> float:
    """TDEE = BMR x activity multiplier + extra burn estimate."""
    multiplier = ACTIVITY_MULTIPLIER.get(day_type, 1.2)
    extra      = EXTRA_BURN.get(day_type, 0)
    return round(bmr * multiplier + extra)


def macros_for_day(tdee: float, day_type: str, protein_g: int = None) -> dict:
    """
    Returns macro targets using fixed gram targets per day type.
    Calories are computed from macros, not the other way around.
    """
    targets = MACRO_TARGETS.get(day_type, MACRO_TARGETS["easy"])
    p_g = protein_g if protein_g else targets["protein_g"]
    c_g = targets["carbs_g"]
    f_g = targets["fat_g"]

    total_cal = (c_g * 4) + (p_g * 4) + (f_g * 9)

    return {
        "calories":    total_cal,
        "carbs_g":     c_g,
        "protein_g":   p_g,
        "fat_g":       f_g,
        "carb_pct":    round((c_g * 4) / total_cal * 100) if total_cal > 0 else 0,
        "protein_pct": round((p_g * 4) / total_cal * 100) if total_cal > 0 else 0,
        "fat_pct":     round((f_g * 9) / total_cal * 100) if total_cal > 0 else 0,
    }


def classify_activity(
    activity_type: str,
    distance_miles: float = 0.0,
    avg_hr: float = None,
    moving_time_sec: int = 0,
) -> str:
    """
    Classify any Strava activity type into a day type.
    Returns one of: rest, easy, moderate, hard, long
    """
    if not activity_type or activity_type not in TRAINING_TYPES:
        return "rest"

    if activity_type in LOW_INTENSITY_TYPES:
        return "easy" if moving_time_sec >= 1800 else "rest"

    if activity_type in STRENGTH_TYPES:
        return _classify_strength(avg_hr, moving_time_sec)

    if activity_type in ("Run", "VirtualRun", "TrailRun"):
        return classify_day(distance_miles, avg_hr, moving_time_sec)

    return _classify_cardio(avg_hr, moving_time_sec)


def _classify_strength(avg_hr: float, moving_time_sec: int) -> str:
    duration_min = moving_time_sec / 60
    if duration_min < 30:
        return "easy"
    if avg_hr:
        hr_pct = avg_hr / EST_MAX_HR
        if hr_pct >= 0.75:   return "hard"
        elif hr_pct >= 0.60: return "moderate"
        else:                return "easy"
    if duration_min >= 90:   return "hard"
    elif duration_min >= 45: return "moderate"
    else:                    return "easy"


def _classify_cardio(avg_hr: float, moving_time_sec: int) -> str:
    duration_min = moving_time_sec / 60
    if moving_time_sec >= 5400:
        return "long"
    if avg_hr:
        hr_pct = avg_hr / EST_MAX_HR
        if hr_pct < 0.65:   return "easy"
        elif hr_pct < 0.75: return "moderate"
        else:               return "hard"
    if duration_min >= 75:  return "moderate"
    elif duration_min >= 30: return "easy"
    else:                   return "rest"


def classify_day(
    distance_miles: float = 0.0,
    avg_hr: float = None,
    moving_time_sec: int = 0,
) -> str:
    """Classify a completed run. Returns one of: rest, easy, moderate, hard, long"""
    if distance_miles < 2.0:
        return "rest"
    if distance_miles >= 10.0 or moving_time_sec >= 5400:
        return "long"
    if avg_hr:
        hr_pct = avg_hr / EST_MAX_HR
        if hr_pct < 0.65:   return "easy"
        elif hr_pct < 0.75: return "moderate" if distance_miles >= 5.0 else "easy"
        else:               return "hard"
    if distance_miles < 5.0:   return "easy"
    elif distance_miles < 8.0: return "moderate"
    else:                      return "hard"


def classify_runna_event(title: str) -> str:
    """Parse a Runna Google Calendar event title into a day type."""
    if not title:
        return "rest"
    t = title.lower()

    if any(k in t for k in ["rest", "cross training", "cross-training", "off"]):
        return "rest"
    if any(k in t for k in ["long run", "long easy"]):
        mins = _extract_minutes(title)
        if mins and mins < 60: return "moderate"
        return "long"
    if any(k in t for k in ["tempo", "interval", "intervals", "fartlek",
                              "hill repeat", "hills", "speed", "track",
                              "race", "time trial", "threshold"]):
        return "hard"
    if any(k in t for k in ["easy", "recovery", "shakeout", "jog"]):
        km = _extract_km(title)
        miles = km * 0.621371 if km else 0
        mins = _extract_minutes(title)
        if miles >= 10 or (mins and mins >= 90): return "long"
        return "easy"
    if any(k in t for k in ["progression", "steady", "aerobic", "general aerobic"]):
        km = _extract_km(title)
        miles = km * 0.621371 if km else 0
        if miles >= 10: return "long"
        return "moderate"

    km = _extract_km(title)
    miles = km * 0.621371 if km else 0
    mins = _extract_minutes(title)
    if miles >= 10 or (mins and mins >= 90):    return "long"
    elif miles >= 6 or (mins and mins >= 50):   return "moderate"
    elif miles > 0 or (mins and mins > 0):      return "easy"
    return "easy"


def _extract_km(text: str) -> float:
    m = re.search(r'(\d+(?:\.\d+)?)\s*km', text, re.IGNORECASE)
    return float(m.group(1)) if m else 0.0


def _extract_minutes(text: str) -> int:
    m = re.search(r'(\d+):(\d{2})', text)
    if m: return int(m.group(1)) * 60 + int(m.group(2))
    m = re.search(r'(\d+)\s*min', text, re.IGNORECASE)
    if m: return int(m.group(1))
    return 0


TIMING = {
    "rest": {
        "label":   "Rest / Recovery",
        "color":   "red",
        "summary": "Low carb day. Protein stays high. Let your body recover and rebuild.",
        "pre":     None,
        "during":  None,
        "post":    "Prioritize protein within 60 min of waking — 40-50g. Eggs, Greek yogurt, cottage cheese, or a protein shake. Keep carbs light throughout the day.",
        "notes":   "Rest days are where adaptation happens. Hit your 200g protein target and resist the urge to eat back training calories. 150g carbs is enough to top off glycogen without excess.",
    },
    "easy": {
        "label":   "Easy Run / Light Training",
        "color":   "yellow",
        "summary": "Moderate carb day. Light fueling around the workout, protein anchor stays strong.",
        "pre":     "30-60 min before: light carb snack if needed — banana, half a bagel, or rice cake. Skip if running within 30 min of waking.",
        "during":  "Water only for efforts under 60 min. Electrolytes if hot outside.",
        "post":    "Within 45 min: 40-50g protein + moderate carbs. Greek yogurt with fruit, protein shake with oats, or eggs with toast.",
        "notes":   "Easy days build your aerobic base. Don't over-fuel — some mild glycogen depletion trains your body to use fat more efficiently.",
    },
    "moderate": {
        "label":   "Moderate Run / Strength",
        "color":   "yellow",
        "summary": "Moderate-high carb day. Intentional pre and post fueling.",
        "pre":     "60-90 min before: 300-400 cal carb-focused meal — oatmeal with protein powder, rice + eggs, or a bagel with turkey. Keep fat and fiber low.",
        "during":  "Cardio 60-90 min: 30-45g carbs/hr. Strength session: water and electrolytes, no carbs needed mid-session.",
        "post":    "Within 30-45 min: 40-50g protein + 60-80g carbs. Rice bowl with chicken, protein shake + banana, or Greek yogurt parfait.",
        "notes":   "312g carbs gives you enough glycogen to perform and recover without excess. Spread protein across 4-5 meals — 40-50g per sitting.",
    },
    "hard": {
        "label":   "Hard / Tempo / Heavy Lifting",
        "color":   "green",
        "summary": "High carb day. Aggressive fueling before and after. Performance depends on glycogen.",
        "pre":     "2-3 hrs before: 500-600 cal carb-rich meal — white rice + lean protein, pasta, or a large bagel with eggs. Low fiber, low fat. 30-45 min before: gel or banana.",
        "during":  "Cardio: 45-60g carbs/hr. Strength: optional 20-30g intra-workout carbs for sessions over 75 min.",
        "post":    "Within 20-30 min: 50g+ protein + 80-100g fast carbs immediately. Chocolate milk + protein shake, rice cakes + protein, or a large recovery shake.",
        "notes":   "The day before a hard session matters as much as the morning of. Today's 412g carb target is partly fueling tomorrow's performance if you have back-to-back hard days.",
    },
    "long": {
        "label":   "Long Run",
        "color":   "green",
        "summary": "Highest carb day. Race-simulation fueling. Practice what you'll do on race day.",
        "pre":     "Night before: carb-rich dinner. 2-3 hrs before: 400-500 cal easy carbs — oatmeal, toast + banana, white rice. Caffeine 45-60 min before.",
        "during":  "45-60g carbs per hour starting at mile 4-5. Use exactly what you'll race with. 500-700 ml fluid/hr. Sodium mandatory beyond 75 min.",
        "post":    "Within 20 min: 50g+ protein + 100g+ fast carbs — non-negotiable. Chocolate milk is legitimate here. Full meal within 90 min. Prioritize sodium to drive rehydration.",
        "notes":   "Long runs suppress appetite for hours after. Set a phone alarm to eat at 20 min post-run even if you're not hungry. Missing this window costs you 2 days of recovery.",
    },
    "strength": {
        "label":   "Strength Training",
        "color":   "green",
        "summary": "High protein, moderate-high carb. Muscle protein synthesis is the priority.",
        "pre":     "60-90 min before: 300-400 cal with 30-40g protein + moderate carbs — protein shake with oats, Greek yogurt + fruit, or eggs + rice.",
        "during":  "Water and electrolytes. Optional: 20-30g fast carbs for sessions over 75 min or heavy compound work.",
        "post":    "Within 30 min: 50g protein + 60-80g carbs. Whey protein + banana, chocolate milk + protein bar, or Greek yogurt + granola.",
        "notes":   "Leucine is the trigger for muscle protein synthesis — prioritize whey, eggs, chicken, or dairy post-workout. Spread the remaining protein across 3-4 meals throughout the day.",
    },
    "rest_push": {
        "label":   "Rest + Push Day (Peloton)",
        "color":   "yellow",
        "summary": "Upper body push session. Moderate carbs to fuel the workout, high protein for muscle repair.",
        "pre":     "60-90 min before: 300-400 cal — protein shake with oats, Greek yogurt + fruit, or eggs + rice. Keep fat and fiber low.",
        "during":  "Water and electrolytes. Optional 20-30g carbs for sessions over 60 min.",
        "post":    "Within 30 min: 40-50g protein + 50-60g carbs. Whey shake + banana, or Greek yogurt + granola.",
        "notes":   "Push days on Peloton (chest, shoulders, triceps) don't tax your legs — good choice for days off from running. Protein timing matters more than carbs here.",
    },
    "rest_pull": {
        "label":   "Rest + Pull Day (Peloton)",
        "color":   "yellow",
        "summary": "Upper body pull session. Protein-forward day — back and biceps respond well to leucine-rich post-workout meals.",
        "pre":     "60 min before: light protein + carbs — protein shake with half a banana, or Greek yogurt.",
        "during":  "Water only. Pull sessions are low cardio demand.",
        "post":    "Within 30 min: 40-50g protein. Whey shake, eggs, or chicken. Moderate carbs (40-50g) to replenish.",
        "notes":   "Pull days are the safest Peloton choice after a hard or long run — zero leg involvement. Great for maintaining upper body strength without compromising run recovery.",
    },
    "rest_legs": {
        "label":   "Rest + Legs Day (Peloton)",
        "color":   "yellow",
        "summary": "Leg strength session. Moderate-high carbs — your legs are working, they need glycogen.",
        "pre":     "60-90 min before: 300-400 cal carb + protein — oatmeal with protein, rice + eggs, or a bagel with turkey.",
        "during":  "Water and electrolytes. 20-30g carbs optional for sessions over 60 min.",
        "post":    "Within 30 min: 50g protein + 60-80g carbs. Critical window — legs will be sore if you skip this.",
        "notes":   "Only do leg days on Peloton when you have 2+ days before your next hard or long run. The DOMS from heavy squats and lunges will affect your running if timed poorly.",
    },
    "rest_runners": {
        "label":   "Rest + Strength for Runners (Peloton)",
        "color":   "yellow",
        "summary": "Runner-specific strength. Full body but running-aware — targets stability, posterior chain, and single-leg strength.",
        "pre":     "60 min before: light protein + carbs — banana and protein shake, or Greek yogurt.",
        "during":  "Water. These classes are moderate intensity.",
        "post":    "Within 45 min: 40-50g protein + moderate carbs. Standard recovery meal applies.",
        "notes":   "Strength for Runners with Matt Wilpers and Becs Gentry is the best Peloton program for your goals. The movements are designed to complement running, not compete with it.",
    },
    "rest_core": {
        "label":   "Rest + Core (Peloton)",
        "color":   "red",
        "summary": "Core-only session. Low caloric impact — treat this nutritionally like a rest day.",
        "pre":     None,
        "during":  "Water only.",
        "post":    "Normal protein timing — 40g+ within 60 min of waking. Core work doesn't significantly deplete glycogen.",
        "notes":   "Core sessions (10-15 min) don't change your nutrition needs meaningfully. Hit your 200g protein target and keep carbs at rest day levels.",
    },
    "rest_stretch": {
        "label":   "Rest + Mobility (Peloton)",
        "color":   "red",
        "summary": "Mobility and recovery session. Pure rest day nutrition.",
        "pre":     None,
        "during":  "Stay hydrated.",
        "post":    "Normal rest day eating. Prioritize protein and micronutrients.",
        "notes":   "Mobility work is about tissue quality, not caloric burn. Eat like a rest day — protein high, carbs moderate.",
    },
}
def timing_guidance(day_type: str) -> dict:
    return TIMING.get(day_type, TIMING["easy"])


def plan_day(
    date_str: str,
    weight_kg: float,
    weight_cm: float,
    age: int,
    day_type: str,
    source: str = "strava",
    run_name: str = None,
    run_miles: float = 0.0,
    activity_type: str = None,
    peloton_category: str = None,
) -> dict:
    """
    Compute the complete fuel plan for a single day.
    If peloton_category is provided and day_type is rest, adjusts
    macros and timing to reflect the cross-training load.
    """
    bmr = compute_bmr(weight_kg, weight_cm, age)

    # Adjust effective day type based on Peloton workout
    effective_type = day_type
    timing_key     = day_type
    display_type   = day_type

    if peloton_category and day_type == "rest":
        fuel_type = PELOTON_FUEL_MAP.get(peloton_category, "rest")
        effective_type = fuel_type
        timing_key     = "rest_" + peloton_category  # use specific timing if available
        display_type   = "rest_" + peloton_category  # for color/label lookup

    tdee   = tdee_for_day(bmr, effective_type)
    macros = macros_for_day(tdee, effective_type)

    # Get timing — prefer specific Peloton timing, fall back to effective type
    if activity_type in STRENGTH_TYPES and not peloton_category:
        timing = TIMING.get("strength", timing_guidance(effective_type))
    else:
        timing = TIMING.get(timing_key, timing_guidance(effective_type))

    return {
        "date":             date_str,
        "day_type":         day_type,          # original classification
        "effective_type":   effective_type,    # what macros are based on
        "display_type":     display_type,      # what to show in UI
        "color":            DAY_TYPE_COLOR.get(display_type, DAY_TYPE_COLOR.get(day_type, "yellow")),
        "source":           source,
        "run_name":         run_name,
        "run_miles":        run_miles,
        "activity_type":    activity_type,
        "peloton_category": peloton_category,
        "bmr":              round(bmr),
        "tdee":             tdee,
        "macros":           macros,
        "timing":           timing
    }


if __name__ == "__main__":
    WEIGHT = float(_read_env("ATHLETE_WEIGHT_KG", "73"))
    HEIGHT_CM = float(_read_env("ATHLETE_HEIGHT_CM", "175"))
    AGE = int(_read_env("ATHLETE_AGE", "27"))

    print("=" * 60)
    print("STRIDE FUEL ENGINE — SELF TEST")
    print(f"Athlete: {WEIGHT} kg, {HEIGHT_CM} cm, age {AGE}")
    print(f"BMR: {round(compute_bmr(WEIGHT, HEIGHT_CM, AGE))} kcal/day")
    print("=" * 60)

    for dt in DAY_TYPES:
        plan = plan_day("2026-05-14", WEIGHT, HEIGHT_CM, AGE, dt, source="test")
        m = plan["macros"]
        print(f"\n[{dt.upper()}]  {m['calories']} kcal")
        print(f"  Carbs:   {m['carbs_g']}g  ({m['carb_pct']}%)")
        print(f"  Protein: {m['protein_g']}g  ({m['protein_pct']}%)")
        print(f"  Fat:     {m['fat_g']}g  ({m['fat_pct']}%)")

    print("\n" + "=" * 60)
    print("ACTIVITY CLASSIFIER TEST")
    print("=" * 60)
    test_activities = [
        ("WeightTraining", 0,    155, 3600, "60 min lifting, HR 155"),
        ("WeightTraining", 0,    130, 2700, "45 min lifting, HR 130"),
        ("Crossfit",       0,    168, 2400, "40 min CrossFit, HR 168"),
        ("Run",            6.5,  145, 3600, "6.5mi run, HR 145"),
        ("Run",            12.0, 138, 6600, "12mi long run, HR 138"),
        ("Ride",           0,    142, 7200, "2hr bike ride, HR 142"),
        ("Walk",           0,    None,3600, "1hr walk"),
        ("Yoga",           0,    None,3600, "1hr yoga"),
        ("Workout",        0,    None,2400, "40 min workout no HR"),
    ]
    for atype, miles, hr, secs, label in test_activities:
        result = classify_activity(atype, miles, hr, secs)
        print(f"  {label:<42} -> {result}")
