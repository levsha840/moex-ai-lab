# 09_DECISIONS — MOEX AI LAB

## ADR-001 — CONTROL_CENTER as source of truth
Decision: use CONTROL_CENTER as the only project state source.
Status: accepted.

## ADR-002 — Patch-based delivery
Decision: multi-file project updates are delivered as patch packages.
Status: accepted.

## ADR-003 — Intraday candles table separate from daily/generic candles
Decision: v1.1 introduces `candles_intraday` instead of overloading existing `candles` table.
Status: accepted.
Reason: intraday data has higher volume and needs explicit lifecycle/indexing.

## ADR-004 — Repository isolation
Decision: database access for intraday candles is isolated in `IntradayRepository`.
Status: accepted.
