import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.append(str(ROOT))

import argparse
from core.strategy.lifecycle import StrategyLifecycleManager, VALID_STATUSES

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--status", choices=sorted(VALID_STATUSES), required=True)
    p.add_argument("--reason", default="")
    a = p.parse_args()
    StrategyLifecycleManager().set_status(a.id, a.status, a.reason)
    print(f"Strategy {a.id} moved to {a.status}")

if __name__ == "__main__":
    main()
