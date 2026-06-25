import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.append(str(ROOT))

from core.broker.adapters import TInvestSandboxBroker

def main():
    print(TInvestSandboxBroker().place_order("TEST", "BUY", 1, 100))

if __name__ == "__main__":
    main()
