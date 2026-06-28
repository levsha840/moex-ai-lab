"""Generic experiment infrastructure shared by all parameterised hypotheses.

Hypothesis-specific code lives in experiments/h_<name>/providers.py, which subclasses
GenericProviderFactory and sets class-level signal_type / hold_bars / signal_params.
"""
