"""levelprobs — recency-weighted intraday level-hit probabilities for ES/NQ/SPX.

Public surface:
    from levelprobs import analyze
    result_text = analyze("ES")          # synthetic demo
    print(result_text)
"""
from .api import analyze   # noqa: F401

__all__ = ["analyze"]
