"""
Spaced Repetition System (SRS) algorithm - "Longevity" intervals.

This module implements a rigid interval-based SRS system with fixed steps.
The intervals progressively increase from 1 day to 3 years.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Tuple

# Rigid "Longevity" intervals in minutes
# [1d, 1w, 1m, 3m, 6m, 12m, 18m, 24m, 36m]
INTERVALS_MINUTES = [
    1440,       # 1 day
    10080,      # 1 week
    43200,      # 1 month (30 days)
    129600,     # 3 months
    262800,     # 6 months
    525600,     # 12 months (1 year)
    788400,     # 18 months
    1051200,    # 24 months (2 years)
    1576800,    # 36 months (3 years)
]

# Period labels matching the intervals
PERIOD_LABELS = [
    "1_day",
    "1_week",
    "1_month",
    "3_months",
    "6_months",
    "12_months",
    "18_months",
    "24_months",
    "36_months",
]

# Delay labels for user-facing step selection (includes "now")
DELAY_LABELS = ["now"] + PERIOD_LABELS

# Maximum step (0-indexed)
MAX_STEP = len(INTERVALS_MINUTES) - 1


class ReviewRating(str, Enum):
    """Review rating options for flashcard review."""
    FORGOT = "forgot"
    HARD = "hard"
    GOOD = "good"


@dataclass
class SRSUpdate:
    """Result of an SRS calculation after a review."""
    step: int
    next_review_at: datetime
    interval_minutes: int
    review_count: int


def calculate_next_review(
    current_step: int,
    review_count: int,
    rating: ReviewRating,
) -> SRSUpdate:
    """
    Calculate the next review state based on the rating.

    Algorithm:
    - FORGOT: Reset to step 0, next_review = NOW + 1 day
    - HARD: Keep current step, next_review = NOW + current interval
    - GOOD: Increment step (max 8), next_review = NOW + new interval

    Args:
        current_step: Current step level (0-8)
        review_count: Current review count
        rating: The user's rating of their recall

    Returns:
        SRSUpdate with new step, next_review_at, interval_minutes, and review_count
    """
    now = datetime.now(timezone.utc)
    new_review_count = review_count + 1

    if rating == ReviewRating.FORGOT:
        # Reset to step 0, schedule for 1 day later
        new_step = 0
        new_interval = INTERVALS_MINUTES[0]  # 1 day
    elif rating == ReviewRating.HARD:
        # Stay at current step, use current interval
        new_step = current_step
        new_interval = INTERVALS_MINUTES[new_step]
    elif rating == ReviewRating.GOOD:
        # Advance to next step (capped at max)
        new_step = min(current_step + 1, MAX_STEP)
        new_interval = INTERVALS_MINUTES[new_step]
    else:
        # Default to HARD behavior
        new_step = current_step
        new_interval = INTERVALS_MINUTES[new_step]

    next_review_at = now + timedelta(minutes=new_interval)

    return SRSUpdate(
        step=new_step,
        next_review_at=next_review_at,
        interval_minutes=new_interval,
        review_count=new_review_count,
    )


def get_interval_display(interval_minutes: int) -> str:
    """
    Convert interval in minutes to human-readable format.

    Args:
        interval_minutes: Interval in minutes

    Returns:
        Human-readable string (e.g., "1 day", "1 week", "3 months")
    """
    if interval_minutes < 1440:
        hours = interval_minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    elif interval_minutes < 10080:
        days = interval_minutes // 1440
        return f"{days} day{'s' if days != 1 else ''}"
    elif interval_minutes < 43200:
        weeks = interval_minutes // 10080
        return f"{weeks} week{'s' if weeks != 1 else ''}"
    elif interval_minutes < 525600:
        months = interval_minutes // 43200
        return f"{months} month{'s' if months != 1 else ''}"
    else:
        months = interval_minutes // 43200
        return f"{months} months"


def get_period_label(step: int) -> str:
    """
    Get the period label for a given step.

    Args:
        step: The SRS step (0-8)

    Returns:
        Period label string
    """
    if 0 <= step < len(PERIOD_LABELS):
        return PERIOD_LABELS[step]
    return PERIOD_LABELS[-1]


def get_initial_srs_state() -> Tuple[int, datetime, int]:
    """
    Get initial SRS state for a new flashcard.

    Returns:
        Tuple of (step, next_review_at, interval_minutes)
    """
    return (
        0,
        datetime.now(timezone.utc),
        INTERVALS_MINUTES[0],
    )


def get_srs_state_for_step(step: int) -> Tuple[int, datetime, int]:
    """
    Get SRS state for a specific step.

    Step 0 with next_review_at=NOW means "due now".
    Steps 0-8 schedule the card at the corresponding interval from now.

    Args:
        step: The target step (0-8)

    Returns:
        Tuple of (step, next_review_at, interval_minutes)
    """
    clamped_step = max(0, min(step, MAX_STEP))
    interval = INTERVALS_MINUTES[clamped_step]
    next_review_at = datetime.now(timezone.utc) + timedelta(minutes=interval)
    return (clamped_step, next_review_at, interval)


def delay_label_to_step(label: str) -> Tuple[int, bool]:
    """
    Convert a delay label to a step and whether it's due now.

    Args:
        label: One of DELAY_LABELS ("now", "1_day", "1_week", etc.)

    Returns:
        Tuple of (step, is_due_now)
    """
    if label == "now":
        return (0, True)
    if label in PERIOD_LABELS:
        return (PERIOD_LABELS.index(label), False)
    return (0, True)
