"""
Asset Recommendations (Tier 8 — Asset Intelligence Runtime)
"""

from .asset_recommendation_engine import (
    AssetRecommendationResult,
    AssetRecommendationEngine,
    get_asset_recommendation_engine,
    reset_asset_recommendation_engine_for_tests,
)

__all__ = [
    "AssetRecommendationResult",
    "AssetRecommendationEngine",
    "get_asset_recommendation_engine",
    "reset_asset_recommendation_engine_for_tests",
]
