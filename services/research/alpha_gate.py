"""Alpha Library Gate — research-phase quality criteria.

Reference: docs/70_ALPHA_LIBRARY.md, constraints O-01 through O-09.

The gate is intentionally lenient at the research stage:
  Research gate:   pass_rate >= 0.40  →  CANDIDATE_RESEARCH_PASSED
  Paper gate:      pass_rate >= 0.80  →  APPROVED_FOR_PAPER (requires manual risk review)

Separating the thresholds prevents premature dismissal of hypotheses that show
directional edge but haven't yet been tuned for deployment.
"""
from __future__ import annotations

from dataclasses import dataclass


# Alpha Library constraint O-02: minimum out-of-sample pass rate for research stage.
RESEARCH_MIN_PASS_RATE: float = 0.40

# Alpha Library constraint O-01: minimum WF windows to qualify (prevents over-fit on few windows).
RESEARCH_MIN_WINDOWS: int = 5


@dataclass(frozen=True)
class AlphaGateResult:
    """Outcome of a single Alpha Library gate check."""

    passed: bool
    pass_rate: float | None
    windows_total: int
    reason: str

    def __str__(self) -> str:
        mark = "PASS" if self.passed else "FAIL"
        pr = f"{self.pass_rate:.3f}" if self.pass_rate is not None else "n/a"
        return f"[{mark}] pass_rate={pr}, windows={self.windows_total} — {self.reason}"


class AlphaLibraryGate:
    """Checks whether a research result meets Alpha Library minimum criteria.

    Criteria applied (in order):
      1. pass_rate must be available (at least some trades generated)
      2. windows_total >= RESEARCH_MIN_WINDOWS (enough statistical coverage)
      3. pass_rate >= RESEARCH_MIN_PASS_RATE (directional edge present)
    """

    def __init__(
        self,
        min_pass_rate: float = RESEARCH_MIN_PASS_RATE,
        min_windows: int = RESEARCH_MIN_WINDOWS,
    ) -> None:
        self.min_pass_rate = min_pass_rate
        self.min_windows = min_windows

    def check(
        self,
        pass_rate: float | None,
        windows_total: int,
    ) -> AlphaGateResult:
        if pass_rate is None:
            return AlphaGateResult(
                passed=False,
                pass_rate=None,
                windows_total=windows_total,
                reason="pass_rate not available (no trades generated in test windows)",
            )
        if windows_total < self.min_windows:
            return AlphaGateResult(
                passed=False,
                pass_rate=pass_rate,
                windows_total=windows_total,
                reason=(
                    f"windows_total={windows_total} < {self.min_windows} "
                    f"(O-01: insufficient coverage)"
                ),
            )
        if pass_rate < self.min_pass_rate:
            return AlphaGateResult(
                passed=False,
                pass_rate=pass_rate,
                windows_total=windows_total,
                reason=(
                    f"pass_rate={pass_rate:.3f} < {self.min_pass_rate:.2f} "
                    f"(O-02: below research threshold)"
                ),
            )
        return AlphaGateResult(
            passed=True,
            pass_rate=pass_rate,
            windows_total=windows_total,
            reason=(
                f"pass_rate={pass_rate:.3f} >= {self.min_pass_rate:.2f} "
                f"over {windows_total} windows"
            ),
        )
