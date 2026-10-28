from dataclasses import dataclass
from typing import Final

ENGINE_VERSION: Final[str] = "1.0.0"


@dataclass(frozen=True)
class RiskWeights:
    attendance: float = 0.30
    marks: float = 0.25
    backlogs: float = 0.15
    trend: float = 0.12
    assignments: float = 0.10
    engagement: float = 0.08

    def as_dict(self) -> dict[str, float]:
        return {
            "attendance": self.attendance,
            "marks": self.marks,
            "backlogs": self.backlogs,
            "trend": self.trend,
            "assignments": self.assignments,
            "engagement": self.engagement,
        }


@dataclass(frozen=True)
class RiskThresholds:
    low_upper: float = 39.9
    medium_upper: float = 69.9
    high_lower: float = 70.0
    downgrade_margin: float = 3.0  # Hysteresis buffer
    min_confidence: float = 0.50  # Confidence floor for numeric levels
    min_classes_held: int = 20  # Minimum sample size for attendance
    attendance_override_threshold: float = 50.0  # att < 50 -> score >= 70
    backlogs_high_override: int = 4  # backlogs >= 4 -> score >= 70
    backlogs_med_override: int = 2  # backlogs >= 2 -> score >= 40
    trend_critical_risk: float = 80.0  # trend >= 80 -> watchlist = True


default_weights = RiskWeights()
default_thresholds = RiskThresholds()
