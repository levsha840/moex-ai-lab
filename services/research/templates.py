from experiments.h13_adx_continuation.template import H13_TEMPLATE
from core.hypothesis_generator.models import HypothesisTemplate

# Templates available in Research Service Alpha.
# Extension point EP-02: add new HypothesisTemplate here to include it in generation.
ALPHA_TEMPLATES: list[HypothesisTemplate] = [H13_TEMPLATE]
