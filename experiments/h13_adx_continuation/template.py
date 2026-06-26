"""HypothesisTemplate for H-13 ADX Trend Continuation with RSI Pullback."""
from core.hypothesis_generator.models import HypothesisPriority, HypothesisTemplate

H13_TEMPLATE = HypothesisTemplate(
    template_id="tmpl_h13_adx_continuation",
    name="ADX Trend Continuation with RSI Pullback",
    category="Trend Following",
    priority=HypothesisPriority.A,
    title_template=(
        "H-13 ADX Continuation on {ticker} "
        "({regime} + RSI pullback [{rsi_low}–{rsi_high}])"
    ),
    statement_template=(
        "When the market regime is {regime} (ADX > {adx_threshold}, "
        "SMA({sma_fast}) > SMA({sma_slow})) and RSI({rsi_period}) retraces "
        "to the neutral zone [{rsi_low}, {rsi_high}], the price continues in "
        "the direction of the prevailing trend — generating a profitable long "
        "entry on {ticker} with a {hold_bars}-bar time exit."
    ),
    required_features=["adx_14", "rsi_14", "sma_20", "sma_50", "atr_14"],
    default_parameters={
        "ticker": "SBER",
        "regime": "TREND_UP",
        "adx_threshold": 25,
        "sma_fast": 20,
        "sma_slow": 50,
        "rsi_period": 14,
        "rsi_low": 40,
        "rsi_high": 60,
        "hold_bars": 5,
    },
)
