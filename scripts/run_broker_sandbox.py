#!/usr/bin/env python3
"""M12.5 — Broker Sandbox CLI.

All commands operate against the T-Invest Sandbox (safe, no real money).
Live trading is NEVER enabled here.

Usage:
  python scripts/run_broker_sandbox.py --health
  python scripts/run_broker_sandbox.py --account
  python scripts/run_broker_sandbox.py --positions
  python scripts/run_broker_sandbox.py --balance
  python scripts/run_broker_sandbox.py --journal [--tail 20]
  python scripts/run_broker_sandbox.py --place-test-order SBER 1 258.00
  python scripts/run_broker_sandbox.py --cancel-all
  python scripts/run_broker_sandbox.py --mock --health   (use MockBroker offline)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

JOURNAL_PATH = ROOT / "runtime" / "trade_journal.jsonl"


def _make_broker(use_mock: bool = False):
    from services.broker import MockBroker, TInvestSandboxAdapter
    if use_mock:
        b = MockBroker()
        b.connect()
        return b
    token = os.getenv("T_INVEST_TOKEN", "")
    if not token:
        print("[WARN] T_INVEST_TOKEN not set — falling back to MockBroker")
        b = MockBroker()
        b.connect()
        return b
    b = TInvestSandboxAdapter(token=token)
    b.connect()
    return b


def cmd_health(args) -> None:
    broker = _make_broker(args.mock)
    report = broker.health()
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_account(args) -> None:
    broker = _make_broker(args.mock)
    acc = broker.get_account()
    print(json.dumps(acc.to_dict(), indent=2, ensure_ascii=False))


def cmd_positions(args) -> None:
    broker = _make_broker(args.mock)
    positions = broker.get_positions()
    if not positions:
        print("No open positions.")
        return
    for p in positions:
        print(json.dumps(p.to_dict(), ensure_ascii=False))


def cmd_balance(args) -> None:
    broker = _make_broker(args.mock)
    balances = broker.get_balance()
    for b in balances:
        print(json.dumps(b.to_dict(), ensure_ascii=False))


def cmd_journal(args) -> None:
    from services.broker import TradeJournal
    j = TradeJournal(JOURNAL_PATH)
    entries = j.tail(args.tail)
    if not entries:
        print("Journal is empty.")
        return
    for e in entries:
        ts   = e.get("ts", "")[:19]
        evt  = e.get("event", "")
        oid  = e.get("order_id", "")[:12]
        strat = e.get("strategy_id", "")
        print(f"[{ts}] {evt:<22} order={oid}  strategy={strat}")
    print(f"\n({len(entries)} shown, total={j.count()})")


def cmd_place_test_order(args) -> None:
    from services.broker import MockBroker, OrderRequest, OrderSide, OrderType, TradeJournal, RiskGuard, RiskConfig

    instrument = args.instrument
    quantity   = int(args.quantity)
    price      = float(args.price)

    broker = _make_broker(args.mock)
    journal = TradeJournal(JOURNAL_PATH)
    risk_guard = RiskGuard(RiskConfig(sandbox_only=True, max_position_size=100))

    request = OrderRequest(
        instrument=instrument,
        side=OrderSide.BUY,
        quantity=quantity,
        price=price,
        strategy_id="CLI_TEST",
        cycle_id="cli_manual",
    )

    open_positions = len(broker.get_positions())
    check = risk_guard.check(request, open_positions=open_positions, broker_is_sandbox=broker.is_sandbox)

    if not check:
        print(f"[BLOCKED] {check.rule}: {check.reason}")
        journal.record_rejection("none", check.rule, check.reason, "CLI_TEST", "cli_manual")
        return

    order = broker.place_order(request)
    journal.record_order(order, event="ORDER_PLACED", reason="CLI test order")
    risk_guard.record_order()
    print(f"[OK] Order placed:")
    print(json.dumps(order.to_dict(), indent=2, ensure_ascii=False))


def cmd_cancel_all(args) -> None:
    broker = _make_broker(args.mock)
    journal = TradeJournal(JOURNAL_PATH)
    orders = broker.get_orders()
    from services.broker import OrderStatus
    cancellable = [o for o in orders if o.status in (OrderStatus.ACCEPTED, OrderStatus.PENDING)]
    if not cancellable:
        print("No cancellable orders.")
        return
    for order in cancellable:
        ok = broker.cancel_order(order.order_id)
        print(f"  {'[CANCELLED]' if ok else '[FAILED]'} {order.order_id} {order.instrument}")
        if ok:
            journal.update_order(order.order_id, OrderStatus.CANCELLED)
    print(f"Attempted to cancel {len(cancellable)} order(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="MOEX AI Lab — Broker Sandbox CLI")
    parser.add_argument("--mock", action="store_true", help="Use MockBroker (offline)")
    parser.add_argument("--tail", type=int, default=20)

    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("health",    help="Check broker connection health")
    sub.add_parser("account",   help="Show account info")
    sub.add_parser("positions", help="List open positions")
    sub.add_parser("balance",   help="Show cash balance")
    sub.add_parser("journal",   help="Show trade journal")
    sub.add_parser("cancel-all", help="Cancel all open orders")

    p_order = sub.add_parser("place-test-order", help="Place a test order")
    p_order.add_argument("instrument", help="Instrument FIGI or ticker")
    p_order.add_argument("quantity", type=int, help="Number of lots")
    p_order.add_argument("price", type=float, help="Limit price")

    # Allow top-level flags as shorthand
    parser.add_argument("--health",     action="store_true")
    parser.add_argument("--account",    action="store_true")
    parser.add_argument("--positions",  action="store_true")
    parser.add_argument("--balance",    action="store_true")
    parser.add_argument("--journal",    action="store_true")
    parser.add_argument("--cancel-all", dest="cancel_all", action="store_true")
    parser.add_argument("--place-test-order", dest="place_test_order", nargs=3,
                        metavar=("INSTRUMENT", "QUANTITY", "PRICE"))

    args = parser.parse_args()

    # Subcommand dispatch
    if args.cmd == "health":            cmd_health(args)
    elif args.cmd == "account":         cmd_account(args)
    elif args.cmd == "positions":       cmd_positions(args)
    elif args.cmd == "balance":         cmd_balance(args)
    elif args.cmd == "journal":         cmd_journal(args)
    elif args.cmd == "cancel-all":      cmd_cancel_all(args)
    elif args.cmd == "place-test-order":
        args.instrument = args.instrument
        args.quantity   = args.quantity
        args.price      = args.price
        cmd_place_test_order(args)
    # Top-level flags
    elif args.health:                   cmd_health(args)
    elif args.account:                  cmd_account(args)
    elif args.positions:                cmd_positions(args)
    elif args.balance:                  cmd_balance(args)
    elif args.journal:                  cmd_journal(args)
    elif args.cancel_all:               cmd_cancel_all(args)
    elif args.place_test_order:
        args.instrument, args.quantity, args.price = args.place_test_order
        cmd_place_test_order(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
