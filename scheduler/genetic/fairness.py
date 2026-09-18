"""
Fairness & Priority utilities for ChronosFair GAs
===================================================
Shared by all three genetic algorithms (Course / Exam / Invigilation):

1. PRIORITY      — teachers declare per-slot availability + a preference
                   level (1=strongly avoid .. 10=strongly prefer). The GAs
                   turn this into a soft reward so high-priority wishes win
                   when ties are broken.

2. FAIRNESS      — Jain's Fairness Index (JFI) over workload vectors.
                   JFI = (sum x)^2 / (n * sum x^2)  in (0, 1], 1.0 = perfect
                   equality. We expose both the index and a *penalty* form
                   (1 - JFI) that plugs straight into GA fitness.

3. Workload models:
   - teacher weekly teaching load (course GA)
   - teacher invigilation load   (invigilation GA)

All functions are pure-python and ORM-free so they are trivially testable
and reusable from the Repair module as well.
"""
from collections import defaultdict
from math import sqrt


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------

def preference_reward(preference_level, scale=0.5):
    """Map a 1..10 preference level to a soft reward contribution.

    level 10 (strongly prefer) -> +scale
    level 5  (neutral)         ->  0
    level 1  (strongly avoid)  -> -scale
    Returned value is meant to be ADDED to a raw fitness numerator; callers
    normalise, so `scale` controls how strongly priority bends the GA
    compared with hard-clash penalties.
    """
    if preference_level is None:
        return 0.0
    return scale * (preference_level - 5) / 5.0


def unavailable_penalty(is_available, weight=2.0):
    """Hard-ish soft penalty: scheduling a teacher who marked themselves
    unavailable costs `weight` (kept separate from the binary clash
    penalties so supervisors can tune priorities independently)."""
    return 0.0 if is_available else weight


# ---------------------------------------------------------------------------
# Fairness — Jain's index
# ---------------------------------------------------------------------------

def jain_index(loads):
    """Jain's Fairness Index for a list of non-negative loads.

    JFI = (Σx)² / (n·Σx²)   ∈ (0, 1];  1.0 means perfectly fair.
    An empty or all-zero vector is defined as perfectly fair (1.0).
    """
    n = len(loads)
    if n == 0:
        return 1.0
    total = float(sum(loads))
    sq_total = float(sum(x * x for x in loads))
    if sq_total == 0.0:
        return 1.0
    return (total * total) / (n * sq_total)


def fairness_penalty(loads):
    """1 - JFI  ∈ [0, 1). 0 = perfectly fair."""
    return 1.0 - jain_index(loads)


def normalized_loads(raw_loads, capacities):
    """Express each load as a fraction of the teacher's capacity so a
    professor with max 18 h and a visiting faculty with max 9 h are compared
    on equal footing."""
    out = []
    for load, cap in zip(raw_loads, capacities):
        cap = cap or 1
        out.append(load / cap)
    return out


def workload_fairness_penalty(raw_loads, capacities=None):
    """Fairness penalty over capacity-normalized loads (falls back to raw
    loads when capacities are unknown)."""
    if capacities:
        loads = normalized_loads(raw_loads, capacities)
    else:
        loads = list(raw_loads)
    return fairness_penalty(loads)


def per_day_spread_penalty(assignments_per_day, target_per_day):
    """Soft penalty for lumpy daily assignment (used by exam GA):
    how far each day count drifts from the ideal even spread."""
    if not assignments_per_day or target_per_day <= 0:
        return 0.0
    return sum(abs(a - target_per_day) for a in assignments_per_day) / len(assignments_per_day)


# ---------------------------------------------------------------------------
# Aggregate fairness reporting (used by fairness snapshots + API)
# ---------------------------------------------------------------------------

def compute_teacher_loads(schedules):
    """schedules: iterable of objects/dicts with teacher_id + duration hours.
    Returns {teacher_id: total_hours}."""
    loads = defaultdict(float)
    for s in schedules:
        tid = s.get('teacher_id') if isinstance(s, dict) else s.teacher_id
        hours = s.get('hours', 1.0) if isinstance(s, dict) else getattr(s, 'hours', 1.0)
        loads[tid] += hours
    return dict(loads)


def fairness_report(loads, capacities=None):
    """One-shot report used by the fairness API endpoint and GA runs."""
    raw = list(loads.values())
    normalized = normalized_loads(raw, capacities) if capacities else raw
    return {
        'jain_index': round(jain_index(normalized), 4),
        'fairness_penalty': round(fairness_penalty(normalized), 4),
        'min_load': round(min(raw), 2) if raw else 0,
        'max_load': round(max(raw), 2) if raw else 0,
        'mean_load': round(sum(raw) / len(raw), 2) if raw else 0,
        'std_load': round(sqrt(fairness_penalty(raw) * (sum(raw) ** 2) / len(raw)), 2) if raw and sum(raw) else 0,
        'teacher_count': len(raw),
    }
