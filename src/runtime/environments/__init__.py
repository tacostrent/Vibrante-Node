"""
Environment Expansion Pack (§39)
=================================
Central module for all 55 production environments across 9 categories.

Public surface:
    EnvironmentDefinition
    EnvironmentRegistry
    get_environment_registry()
    reset_environment_registry_for_tests()

    EnvironmentStatRecord
    EnvironmentStatistics
    get_environment_statistics()
    reset_environment_statistics_for_tests()

    BUILTIN_ENVIRONMENT_NAMES
    ALL_CATEGORIES
    ENV_CATEGORY_*  constants
"""

from src.runtime.environments.environment_registry import (
    EnvironmentDefinition,
    EnvironmentRegistry,
    get_environment_registry,
    reset_environment_registry_for_tests,
    BUILTIN_ENVIRONMENT_NAMES,
    ALL_CATEGORIES,
    ENV_CATEGORY_INDUSTRIAL,
    ENV_CATEGORY_SCIENTIFIC,
    ENV_CATEGORY_MILITARY,
    ENV_CATEGORY_SCI_FI,
    ENV_CATEGORY_URBAN,
    ENV_CATEGORY_INTERIOR,
    ENV_CATEGORY_NATURE,
    ENV_CATEGORY_FANTASY,
    ENV_CATEGORY_POST_APOCALYPTIC,
)

from src.runtime.environments.environment_statistics import (
    EnvironmentStatRecord,
    EnvironmentStatistics,
    get_environment_statistics,
    reset_environment_statistics_for_tests,
)

__all__ = [
    "EnvironmentDefinition",
    "EnvironmentRegistry",
    "get_environment_registry",
    "reset_environment_registry_for_tests",
    "BUILTIN_ENVIRONMENT_NAMES",
    "ALL_CATEGORIES",
    "ENV_CATEGORY_INDUSTRIAL",
    "ENV_CATEGORY_SCIENTIFIC",
    "ENV_CATEGORY_MILITARY",
    "ENV_CATEGORY_SCI_FI",
    "ENV_CATEGORY_URBAN",
    "ENV_CATEGORY_INTERIOR",
    "ENV_CATEGORY_NATURE",
    "ENV_CATEGORY_FANTASY",
    "ENV_CATEGORY_POST_APOCALYPTIC",
    "EnvironmentStatRecord",
    "EnvironmentStatistics",
    "get_environment_statistics",
    "reset_environment_statistics_for_tests",
]
