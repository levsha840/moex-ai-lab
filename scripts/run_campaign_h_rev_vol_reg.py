"""Campaign runner: H-REV-VOL-REG on P1 Universe (14 instruments x 3 periods x 1H).

Usage:
  python scripts/run_campaign_h_rev_vol_reg.py

Output: campaigns/h_rev_vol_reg/campaign_report.json
        campaigns/h_rev_vol_reg/candidates.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path so imports work from any CWD
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from services.research.campaign import (
    CampaignResult,
    CampaignRunner,
    P1_INSTRUMENTS,
    P1_PERIODS,
)

_DATA_DIR = _PROJECT_ROOT / "data"
_OUTPUT_DIR = _PROJECT_ROOT / "campaigns" / "h_rev_vol_reg"
_HYPOTHESIS = "tmpl_h_rev_vol_reg"


def main() -> int:
    print(f"\nH-REV-VOL-REG Campaign — P1 Universe")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")

    runner = CampaignRunner(
        hypothesis_template_id=_HYPOTHESIS,
        data_dir=_DATA_DIR,
        output_dir=_OUTPUT_DIR,
        max_candidates=1,
        pass_threshold=0.80,
        train_size=60,
        test_size=20,
        step_size=20,
        verbose=True,
    )

    result = runner.run(P1_INSTRUMENTS, P1_PERIODS)

    # Save candidates separately for easy downstream use
    _save_candidates(result, _OUTPUT_DIR / "candidates.json")

    print(f"Report: {_OUTPUT_DIR / 'campaign_report.json'}")
    print(f"Candidates: {_OUTPUT_DIR / 'candidates.json'}")
    return 0


def _save_candidates(result: CampaignResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "campaign_id": result.campaign_id,
        "hypothesis_template_id": result.hypothesis_template_id,
        "generated_at": result.generated_at,
        "count": len(result.candidates),
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "instrument": c.instrument,
                "period": c.period,
                "timeframe": c.timeframe,
                "pass_rate": c.pass_rate,
                "confidence": c.confidence,
                "status": c.status.value,
                "source_ref": c.source_ref,
                "created_at": c.created_at,
                "features": c.features,
            }
            for c in result.candidates
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
