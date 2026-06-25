import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import argparse
from core.strategy.lifecycle import StrategyLifecycleManager, VALID_STATUSES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True, help="strategy_catalog id")
    parser.add_argument("--status", type=str, required=True, choices=sorted(VALID_STATUSES))
    parser.add_argument("--reason", type=str, default="")
    args = parser.parse_args()

    StrategyLifecycleManager().set_status(
        strategy_catalog_id=args.id,
        status=args.status,
        reason=args.reason,
    )

    print(f"Strategy {args.id} moved to {args.status}")


if __name__ == "__main__":
    main()
