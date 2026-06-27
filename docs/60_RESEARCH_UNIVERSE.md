# 60_RESEARCH_UNIVERSE
# MOEX AI LAB — Research Universe v1

> Status: **APPROVED** — Source of Truth for instrument selection.
> Era: Research Organization Era (RO).
> Date: 2026-06-27
> Baseline: `v0.9-intelligence-alpha`

---

## Purpose

This document defines the complete research universe of MOEX AI LAB.
Every research campaign, every experiment, every hypothesis must be validated
against instruments and periods defined here.

No instrument outside this universe may be used in an experiment without
a formal amendment to this document.

---

## Tier 1 — Core Universe (28 instruments)

### Selection Criteria

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Free-float market cap | > 50 bn RUB | Ensures real liquidity |
| Average daily turnover (2023) | > 300 mn RUB | Sufficient for institutional trading |
| Data history | ≥ 5 years continuous | Minimum for walk-forward validation |
| Missing bars rate (1H, main session) | < 3% | Data quality gate |
| Exchange listing | MOEX TQBR board | Standardised candle source |
| Suspension history | < 10 trading days / year | Continuity of price series |

### Core Universe Table

| # | Ticker | Company | Sector | Asset Class | Priority |
|---|--------|---------|--------|-------------|----------|
| 01 | SBER | Сбербанк | Banks | Large Cap Equity | P1 — Anchor |
| 02 | LKOH | Лукойл | Oil & Gas | Large Cap Equity | P1 — Anchor |
| 03 | GAZP | Газпром | Oil & Gas | Large Cap Equity | P1 — Anchor |
| 04 | GMKN | Норникель | Metals & Mining | Large Cap Equity | P1 — Anchor |
| 05 | ROSN | Роснефть | Oil & Gas | Large Cap Equity | P1 — Anchor |
| 06 | NVTK | Новатэк | Oil & Gas | Large Cap Equity | P1 — Core |
| 07 | TATN | Татнефть | Oil & Gas | Large Cap Equity | P1 — Core |
| 08 | CHMF | Северсталь | Metals & Mining | Large Cap Equity | P1 — Core |
| 09 | MAGN | ММК | Metals & Mining | Large Cap Equity | P1 — Core |
| 10 | VTBR | ВТБ | Banks | Large Cap Equity | P1 — Core |
| 11 | MGNT | Магнит | Retail | Large Cap Equity | P1 — Core |
| 12 | NLMK | НЛМК | Metals & Mining | Large Cap Equity | P1 — Core |
| 13 | PLZL | Полюс | Metals & Mining | Large Cap Equity | P1 — Core |
| 14 | ALRS | АЛРОСА | Metals & Mining | Large Cap Equity | P1 — Core |
| 15 | MTSS | МТС | Telecom | Large Cap Equity | P2 — Extended |
| 16 | IRAO | Интер РАО | Energy | Large Cap Equity | P2 — Extended |
| 17 | SNGS | Сургутнефтегаз | Oil & Gas | Large Cap Equity | P2 — Extended |
| 18 | FIVE | X5 Group | Retail | Large Cap Equity | P2 — Extended |
| 19 | PHOR | ФосАгро | Chemicals | Large Cap Equity | P2 — Extended |
| 20 | AFLT | Аэрофлот | Transport | Large Cap Equity | P2 — Extended |
| 21 | YDEX | Яндекс | Technology | Large Cap Equity | P2 — Extended |
| 22 | HYDR | РусГидро | Energy | Large Cap Equity | P2 — Extended |
| 23 | MOEX | Московская Биржа | Financial Services | Large Cap Equity | P2 — Extended |
| 24 | FLOT | Совкомфлот | Transport | Large Cap Equity | P2 — Extended |
| 25 | TCSG | Т-Банк (TCS) | Banks | Large Cap Equity | P2 — Extended |
| 26 | RTKM | Ростелеком | Telecom | Large Cap Equity | P3 — Satellite |
| 27 | AKRN | Акрон | Chemicals | Mid Cap Equity | P3 — Satellite |
| 28 | OZON | Озон | Retail | Large Cap Equity | P3 — Satellite |

### Priority Definitions

| Priority | Label | Description | Min campaigns / year |
|----------|-------|-------------|---------------------|
| P1 | Anchor / Core | Highest liquidity, broadest regime coverage | 4+ |
| P2 | Extended | Strong liquidity, sector diversity | 2+ |
| P3 | Satellite | Supplementary; lower liquidity or narrower focus | 1+ |

### Notes on Special Cases

**GAZP** — suspended March–October 2022. Data from those months is flagged
as `SUSPENDED` in dataset metadata. Strategies must handle gap periods.
Use with caution for 2022 research.

**VTBR** — extremely low price per share (sub-1 kopeck as of 2025 after consolidation history).
Percentage returns are valid; absolute price levels are not comparable across years
without adjustment.

**SNGS** — anomalous price behaviour linked to USD cash reserves ("кубышка").
Treat as a special-case instrument; regime detection may produce unusual results.

**TCSG** — listed as TCSG (TCS Group) until 2024, delisted from foreign exchanges.
Renamed to T-Bank. Check ticker availability per period before use.

**OZON** — loss-making; price driven by growth expectations rather than earnings.
P/E-based analysis is not applicable. Volume and momentum strategies only.

**YDEX** — Yandex underwent structural reorganisation in 2024 (Russian entity separated).
Ticker changed. Pre-2024 and post-2024 series are NOT directly comparable.
Flag this discontinuity in all research using YDEX.

---

## Tier 2 — Sector Coverage

### Sector Map

| Sector | Required Tickers | Optional Tickers | Min Coverage |
|--------|-----------------|-----------------|--------------|
| Oil & Gas | LKOH, GAZP, ROSN, NVTK, TATN | SNGS | 4 of 6 |
| Metals & Mining | GMKN, CHMF, MAGN, NLMK, PLZL, ALRS | — | 4 of 6 |
| Banks & Finance | SBER, VTBR | TCSG, MOEX | 2 of 4 |
| Retail | MGNT, FIVE | OZON | 2 of 3 |
| Telecom | MTSS | RTKM | 1 of 2 |
| Energy | IRAO, HYDR | — | 1 of 2 |
| Technology | YDEX | — | 1 of 1 |
| Transport | AFLT, FLOT | — | 1 of 2 |
| Chemicals | PHOR | AKRN | 1 of 2 |

### Sector Weight in Research Matrix

Sectors are weighted by market capitalisation share on MOEX (approximate 2024 figures):

| Sector | Weight | Priority |
|--------|--------|----------|
| Oil & Gas | 40% | Critical — must cover every research campaign |
| Banks & Finance | 18% | Critical — must cover every research campaign |
| Metals & Mining | 15% | High — minimum 4 instruments per campaign |
| Retail | 8% | Medium |
| Technology | 6% | Medium |
| Energy | 5% | Medium |
| Telecom | 3% | Low |
| Transport | 2% | Low |
| Chemicals | 2% | Low |
| Other | 1% | Satellite only |

### Cross-Sector Research Rules

1. A hypothesis validated on Oil & Gas only is labelled **SECTOR-SPECIFIC**.
2. A hypothesis validated on 5+ sectors is labelled **CROSS-SECTOR**.
3. A CROSS-SECTOR label requires a minimum of 10 instruments across at least 4 sectors.
4. Sector concentration exceeding 60% of test instruments **invalidates** a cross-sector claim.

---

## Tier 3 — Macro Universe

### Required Macro Series

| Symbol | Description | MOEX Engine | Board | Timeframe |
|--------|-------------|-------------|-------|-----------|
| IMOEX | Индекс МосБиржи (рублёвый) | stock | SNDX | 1D |
| RGBI | Индекс гособлигаций | stock | SNDX | 1D |
| USD000UTSTOM | Доллар США / Рубль | currency | CETS | 1D |
| CNY000000TOD | Китайский юань / Рубль | currency | CETS | 1D |

### Extended Macro Series

| Symbol | Description | Source | Status |
|--------|-------------|--------|--------|
| Brent (USDBRENT) | Нефть Brent | MOEX commodity or external | Optional — if MOEX provides continuous series |
| GOLD (XAU) | Золото | MOEX commodity or external | Optional |
| RTSI | Индекс РТС (долларовый) | MOEX SNDX engine | Optional — redundant with IMOEX+USDRUB |

### Macro Dependency Rules

| Regime Component | Required Macro Series |
|------------------|-----------------------|
| Trend regime | IMOEX (market direction baseline) |
| Volatility regime | IMOEX (realised volatility) |
| Risk regime | IMOEX + USD/RUB + RGBI (3-vote system) |
| Oil correlation | Brent (if available) |
| FX exposure | USD/RUB mandatory, CNY/RUB recommended |

### Macro Data Availability by Period

| Period | IMOEX | RGBI | USD/RUB | CNY/RUB | Notes |
|--------|-------|------|---------|---------|-------|
| 2019 | Yes | Yes | Yes | Limited | CNY futures low volume in 2019 |
| 2020 | Yes | Yes | Yes | Limited | CNY market thin until 2022 |
| 2021 | Yes | Yes | Yes | Limited | — |
| 2022 | Yes | Yes | Yes | Yes | CNY/RUB market deepened post-sanctions |
| 2023 | Yes | Yes | Yes | Yes | Full coverage |
| 2024 | Yes | Yes | Yes | Yes | Full coverage |
| 2025 | Yes | Yes | Yes | Yes | Ongoing |

---

## Tier 4 — Time Coverage

### Period Definitions

| Period | Label | Market Character | Key Events | Expected Dominant Regime |
|--------|-------|-----------------|------------|--------------------------|
| 2019 | PRE-COVID | Steady growth, low volatility | Oil stable, USD/RUB 63–66 | TREND_UP, LOW_VOL, RISK_ON |
| 2020 | COVID-CRASH | Extreme volatility, V-shape recovery | COVID (Feb–Apr crash), OPEC+ deal (Apr) | HIGH_VOL, mixed RISK (crash then recovery) |
| 2021 | RECOVERY | Inflationary growth, EM rally | Post-COVID rally, commodity super-cycle | TREND_UP, NORMAL_VOL, RISK_ON |
| 2022 | SANCTIONS | Structural break, geopolitical shock | Feb 24 suspension, sanctions cascade | HIGH_VOL, RISK_OFF (H1), anomalous H2 |
| 2023 | ADAPTATION | High rates, dividend-driven | CBR rate at 16%, ruble stabilisation | RANGE, NORMAL_VOL, RISK_ON (selective) |
| 2024 | HIGH-RATE | Rate peak, selective growth | CBR 21%, sector divergence | RANGE, HIGH_VOL (rate-sensitive), mixed |
| 2025 | ONGOING | Rate plateau, normalisation | Rate path uncertain | TBD at runtime |

### Period Flags

| Period | Flag | Research Implication |
|--------|------|---------------------|
| 2022 | `SUSPENDED_TRADING` | GAZP and others suspended. Gaps in data. |
| 2022 | `REGIME_BREAK` | Pre/post break regimes are NOT comparable. |
| 2020 | `EXTREME_VOL` | Vol z-scores > 5σ. Strategy break risk high. |
| 2024 | `PARTIAL_YEAR` | Available data may not cover full year depending on run date. |
| 2025 | `LIVE` | Data is incomplete. Never use as sole validation period. |

### Minimum Period Set for Hypothesis Validation

| Claim | Required Periods |
|-------|-----------------|
| "Strategy works on MOEX" | 2019, 2021, 2023 (3 neutral/positive years) |
| "Strategy is robust" | 2019, 2021, 2023 + at least one stress year (2020 or 2022) |
| "Strategy survives regime breaks" | Must include 2022 |
| "Strategy is not COVID-specific" | Must include 2019 AND 2023 |

---

## Tier 5 — Timeframes

### Timeframe Catalogue

| Timeframe | Label | Bars per Year (est.) | Session | Primary Use |
|-----------|-------|---------------------|---------|-------------|
| 1H | Intraday | ~1700 bars / year (main session) | main (09:00–18:00) | Core research — default |
| 4H | Mid-frequency | ~430 bars / year | main | Swing signals, less noise |
| 1D | Daily | ~247 bars / year | close price | Macro correlation, long-term trends |

### When to Use Each Timeframe

**1H (Primary):**
- All baseline experiments
- Regime detection (21-day rolling window = ~147 bars)
- Correlation with macro (daily close mapped to session close)
- Default for all ExperimentPlan tasks
- All published Autonomous Research reports

**4H (Secondary):**
- When 1H hypothesis validated and we want to test robustness at lower frequency
- When noise-reduction is the explicit research objective
- Cross-timeframe validation: 1H PASS must be confirmed at 4H before claiming robustness

**1D (Tertiary):**
- Macro correlation studies only (default for MacroAgent, CorrelationAgent)
- Long-term regime classification baseline
- NOT used for strategy performance experiments (insufficient bars per period)

### Timeframe Combination Rules

| Combination | Label | Condition |
|-------------|-------|-----------|
| 1H only | INTRADAY-ONLY | Default for single-timeframe experiments |
| 1H + 4H | MULTI-TF | Used when testing frequency robustness |
| 1H + 1D | CROSS-HORIZON | Used when macro-instrument alignment is the hypothesis |
| 4H + 1D | SWING | Not used in v1 (insufficient bars for statistical significance) |

---

## Research Matrix

### Definition

The Research Matrix defines every addressable research cell.
A cell is the intersection of five dimensions:

```
Cell = (Instrument, Period, Timeframe, Regime, Hypothesis)
```

### Matrix Dimensions

| Dimension | Size (v1) | Values |
|-----------|-----------|--------|
| Instrument | 28 | Core Universe (see Tier 1) |
| Period | 7 | 2019–2025 |
| Timeframe | 3 | 1H, 4H, 1D |
| Regime | 9 | 3 trend × 3 volatility × 3 risk (not all 27 cross-products are valid) |
| Hypothesis | N | Open — grows as research progresses |

### Regime Taxonomy

| Dimension | Labels |
|-----------|--------|
| Trend | TREND_UP, TREND_DOWN, RANGE |
| Volatility | LOW_VOL, NORMAL_VOL, HIGH_VOL |
| Risk | RISK_ON, RISK_OFF, RISK_NEUTRAL |

**Valid regime combinations (v1):** Each instrument+period window receives 3 independent
regime labels (one per dimension). A cell may be filtered by any combination:

Examples of valid filter expressions:
- `TREND_UP + LOW_VOL` — bull market, compressed volatility
- `TREND_DOWN + HIGH_VOL + RISK_OFF` — bear market crisis
- `RANGE + NORMAL_VOL` — consolidation (most common in 2023)

### Matrix Size Estimate

| Scope | Instruments | Periods | Timeframes | Approx Cells |
|-------|-------------|---------|------------|--------------|
| Core (P1) | 14 | 5 (2019–2023) | 1 (1H) | ~70 per hypothesis |
| Extended (P1+P2) | 25 | 5 | 1 | ~125 per hypothesis |
| Full (all tiers) | 28 | 7 | 2 | ~392 per hypothesis |
| Full + regimes | 28 | 7 | 2 | ~1176 (×3 regime dims, avg 3 states each) |

### Research Matrix Priorities

Phase 1 research (Autonomous Research Alpha) used:
- 10 instruments (P1 subset), 1 period (2023), 1 timeframe (1H)
- 1 hypothesis (H-ADX-CONTINUATION)
- Total cells explored: 10

Target by end of Research Organization Era:
- 28 instruments, 5+ periods, 2 timeframes
- 10+ active hypotheses
- Total cells: ~2800+ per active hypothesis

---

## Universe Governance

### Inclusion Criteria (full checklist)

An instrument may be added to Core Universe ONLY if all criteria are met:

| Criterion | Gate | Assessment |
|-----------|------|------------|
| MOEX TQBR listing | Hard gate | Automated check via ISS API |
| Average daily volume > 300 mn RUB | Hard gate | Rolling 60-day average |
| Market cap > 50 bn RUB | Hard gate | At time of inclusion |
| Continuous data ≥ 5 years | Hard gate | Less than 10 suspended days/year |
| Missing 1H bars < 3% | Hard gate | Over last 12 months |
| Free float > 15% | Soft gate | Avoid manipulation risk |
| Sector uniqueness | Advisory | Prefer instruments adding new sector exposure |

### Exclusion Criteria

An instrument must be removed if ANY of the following occur:

| Trigger | Action | Timeline |
|---------|--------|---------|
| Delisted from MOEX TQBR | Remove immediately | Within 5 trading days |
| Average daily volume drops below 100 mn RUB (60-day) | Downgrade to P3 | Next quarterly review |
| Average daily volume drops below 50 mn RUB (60-day) | Remove | Within 30 days |
| Missing bars exceed 10% in trailing 3 months | Suspend research | Until data quality restored |
| Trading suspension > 20 days | Flag SUSPENDED, halt new experiments | Duration of suspension |
| Corporate restructuring (merger, split, rebrand) | Review required | Before next experiment |

### Review Cadence

| Review Type | Frequency | Trigger |
|-------------|-----------|---------|
| Liquidity check | Quarterly | Q1, Q2, Q3, Q4 |
| New instrument proposal | Ad hoc | Minimum 2 months stable history required |
| Emergency review | Immediate | Delisting, suspension, corporate event |
| Annual universe refresh | Annually | Full re-assessment against all criteria |

### Amendment Process

To add or remove an instrument:
1. File amendment request in `docs/60_RESEARCH_UNIVERSE.md` (this document) as a PR.
2. Include: liquidity data (last 60 days), history depth, sector rationale.
3. Amendment requires: updated instrument table + updated sector map + updated KPI baselines.
4. No code changes required for universe amendments (data is configuration, not logic).

### Data Quality Standards

| Metric | Warning | Error |
|--------|---------|-------|
| Missing 1H bars | > 1% in trailing 30 days | > 3% |
| Zero-volume bars | > 0.5% in trailing 30 days | > 2% |
| Price spike (>15% intrabar) | Flag for review | Exclude bar from backtest |
| Weekend/holiday bars | Not permitted | Hard filter in MarketAgent |
| After-hours bars | Configurable | Default: excluded (main session only) |

---

## Universe Manager — Design Specification

The Universe Manager is a planned component (not yet implemented).
This section defines its contract for future implementation.

### Responsibilities

| Responsibility | Description |
|---------------|-------------|
| `list_universe(tier, priority)` | Return filtered list of instruments from this document |
| `get_datasets(instrument, period, timeframe)` | Return available dataset paths for a cell |
| `check_liquidity(instrument)` | Verify current liquidity against inclusion criteria |
| `get_sector(instrument)` | Return sector label for an instrument |
| `list_periods(instrument)` | Return periods with valid data for an instrument |
| `validate_cell(instrument, period, timeframe)` | Return True if the cell has sufficient data |
| `sample_experiment_batch(n, tier, period, timeframe)` | Return n instruments for an experiment campaign |

### Interface Contract

```python
# Future agent (RO-X, not yet scheduled)

class UniverseManager:
    def list_universe(
        self,
        tier: Literal["P1", "P2", "P3", "all"] = "P1",
    ) -> tuple[str, ...]:  # returns tickers
        ...

    def get_sector(self, ticker: str) -> str:
        ...

    def list_periods(self, ticker: str) -> tuple[str, ...]:
        # Returns ("2019", "2020", ...) based on data availability
        ...

    def validate_cell(
        self, ticker: str, period: str, timeframe: str
    ) -> bool:
        ...

    def sample_experiment_batch(
        self, n: int, seed: int, tier: str = "P1"
    ) -> tuple[str, ...]:
        # Deterministic sample for reproducible campaigns
        ...
```

### Data Storage

Universe Manager reads from:
- `docs/60_RESEARCH_UNIVERSE.md` (this document) — universe definition
- `data/datasets/` — available datasets per instrument/period
- `data/context/` — macro context

Universe Manager writes to:
- `data/universe/` — cached universe state, liquidity snapshots

### Implementation Priority

Universe Manager is NOT part of Research Organization Era RO-1 through RO-10 roadmap.
It is a prerequisite for scaling research beyond manual campaign configuration.
Planned for a future `RO-INFRA` phase after core agents (RO-2 through RO-10) are complete.

---

## KPI System — Universe Coverage

### Coverage KPIs

| KPI | Definition | Target |
|-----|------------|--------|
| `sector_coverage` | Sectors with ≥1 validated hypothesis / total sectors | ≥ 0.70 by end of RO |
| `period_coverage` | Periods validated for P1 instruments / total periods | ≥ 5 of 7 |
| `instrument_coverage` | Instruments with ≥1 completed campaign / universe size | ≥ 0.50 by end of RO |
| `regime_coverage` | Distinct regime combinations tested / estimated valid combos | ≥ 0.30 |
| `cross_sector_hypotheses` | Hypotheses with CROSS-SECTOR label | ≥ 3 by end of RO |

### Depth KPIs

| KPI | Definition | Target |
|-----|------------|--------|
| `campaigns_per_instrument` | Total campaigns / instrument (P1 tier) | ≥ 4 / year |
| `knowledge_facts_per_sector` | Facts in KnowledgeBase per sector | ≥ 5 per sector |
| `validated_pass_rate_per_instrument` | Instruments with ≥1 PASS experiment | ≥ 5 instruments |
| `contradiction_pairs` | Detected contradictions in KnowledgeBase | Tracked, not targeted |
| `archived_hypotheses` | Hypotheses retired with evidence | ≥ 2 per era |

### Quality KPIs

| KPI | Definition | Target |
|-----|------------|--------|
| `data_completeness_p1` | Missing bars rate across P1 universe | < 1% |
| `multi_period_validation` | Hypotheses validated in ≥3 periods / total active | ≥ 0.50 |
| `regime_stratified_evidence` | Facts with regime label / total facts | ≥ 0.80 |
| `macro_aligned_facts` | Facts with macro context / total facts | ≥ 0.60 |

---

## Seed Campaigns — Recommended Starting Points

To maximise information per research cycle, the following instrument batches
are recommended as starting points for future campaigns.

### Batch A — Oil & Gas Core (6 instruments, 2023, 1H)
`LKOH, GAZP, ROSN, NVTK, TATN, SNGS`
Goal: Test ADX and momentum hypotheses in the dominant MOEX sector.

### Batch B — Banks (3 instruments, 2023, 1H)
`SBER, VTBR, TCSG`
Goal: Validate rate-sensitivity of momentum strategies in high-rate environment (2023).

### Batch C — Metals (5 instruments, 2023, 1H)
`GMKN, CHMF, MAGN, NLMK, PLZL`
Goal: Test commodity-correlated momentum. Cross with Brent / gold macro.

### Batch D — Stress Period (10 instruments, 2020, 1H)
`SBER, LKOH, GMKN, ROSN, NVTK, MGNT, MTSS, IRAO, AFLT, CHMF`
Goal: Validate that confirmed hypotheses survive COVID crash.

### Batch E — Cross-Sector Full (28 instruments, 2023, 1H)
Full Core Universe, single period.
Goal: Cross-sector hypothesis validation. Requires confirmed hypothesis from Batches A–C.

---

## Document Maintenance

This document is reviewed at:
- **Quarterly universe reviews** — liquidity and data quality checks.
- **Era transitions** — full re-assessment before each new era begins.
- **Event-driven amendments** — delisting, suspension, corporate events.

All amendments to Section 1 (Core Universe Table) must be accompanied by:
- Updated liquidity data
- Rationale for change
- Updated sector map (if sector balance changes)
- Updated KPI baselines

The universe composition at time of each major experiment must be recorded
in the experiment's metadata to ensure reproducibility.

---

*Source of Truth for MOEX AI LAB Research Universe.*
*Next review: Q3 2026 (Quarterly Liquidity Check).*
