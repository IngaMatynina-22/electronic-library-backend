"""Progress calculation helpers."""

from __future__ import annotations


def compute_progress_percent(current: int | float, total: int | float) -> float:
    """Return progress percent clamped to [0, 100]."""
    if total is None or total <= 0:
        return 0.0
    value = (float(current) / float(total)) * 100.0
    return max(0.0, min(100.0, round(value, 2)))
