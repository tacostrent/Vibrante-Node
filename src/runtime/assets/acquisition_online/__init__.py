"""
Online Asset Acquisition & Intelligent Asset Fetching (Tier 12.9)
===================================================================
Completes the acquisition loop by adding:
  - Provider session management (Megascans, Fab)
  - Authenticated Megascans search
  - Selective asset downloads (only for semantically-ranked assets)
  - Download queue + scheduler
  - Project-local asset staging
  - Asset provenance tracking
  - Cache-first acquisition pipeline

Public API:
    Singletons:
        get_provider_session_manager()  → ProviderSessionManager
        get_megascans_auth()            → MegascansAuth
        get_megascans_search()          → MegascansSearch
        get_megascans_downloader()      → MegascansDownloader
        get_asset_fetcher()             → AssetFetcher
        get_download_queue()            → DownloadQueue
        get_download_scheduler()        → DownloadScheduler
        get_asset_cache_manager()       → AssetCacheManager
        get_project_asset_staging()     → ProjectAssetStaging
        get_asset_provenance_tracker()  → AssetProvenanceTracker
        get_acquisition_pipeline()      → AcquisitionPipeline
        get_download_review()           → DownloadReview
        get_download_statistics()       → DownloadStatistics
        get_download_serializer()       → DownloadSerializer

    Reset (tests):
        reset_provider_session_manager_for_tests()
        reset_megascans_auth_for_tests()
        reset_megascans_search_for_tests()
        reset_megascans_downloader_for_tests()
        reset_asset_fetcher_for_tests()
        reset_download_queue_for_tests()
        reset_download_scheduler_for_tests()
        reset_asset_cache_manager_for_tests()
        reset_project_asset_staging_for_tests()
        reset_asset_provenance_tracker_for_tests()
        reset_acquisition_pipeline_for_tests()
        reset_download_review_for_tests()
        reset_download_statistics_for_tests()
        reset_download_serializer_for_tests()

    Environment variables:
        VIBRANTE_MEGASCANS_TOKEN  — Megascans/Fab API token (optional)
        VIBRANTE_ASSET_CACHE      — Local cache root directory
        VIBRANTE_PROJECT_STAGING  — Project staging root directory
"""
from __future__ import annotations

# Singletons & types
from .provider_session_manager import (
    ProviderSession,
    ProviderSessionManager,
    get_provider_session_manager,
    reset_provider_session_manager_for_tests,
)
from .megascans_auth import (
    AuthToken,
    MegascansAuth,
    get_megascans_auth,
    reset_megascans_auth_for_tests,
    ENV_MEGASCANS_TOKEN,
    ENV_MEGASCANS_APP_ID,
    ENV_MEGASCANS_APP_KEY,
    ENV_MEGASCANS_USERNAME,
    ENV_MEGASCANS_PASSWORD,
)
from .megascans_search import (
    MegascansSearchRecord,
    MegascansSearch,
    get_megascans_search,
    reset_megascans_search_for_tests,
)
from .megascans_download import (
    DownloadResult,
    MegascansDownloader,
    get_megascans_downloader,
    reset_megascans_downloader_for_tests,
)
from .asset_fetcher import (
    FetchResult,
    AssetFetcher,
    get_asset_fetcher,
    reset_asset_fetcher_for_tests,
)
from .download_queue import (
    DownloadTask,
    DownloadQueue,
    get_download_queue,
    reset_download_queue_for_tests,
)
from .download_scheduler import (
    SchedulerResult,
    DownloadScheduler,
    get_download_scheduler,
    reset_download_scheduler_for_tests,
)
from .asset_cache_manager import (
    CacheEntry,
    AssetCacheManager,
    get_asset_cache_manager,
    reset_asset_cache_manager_for_tests,
    ENV_ASSET_CACHE,
)
from .project_asset_staging import (
    StagingEntry,
    ProjectAssetStaging,
    get_project_asset_staging,
    reset_project_asset_staging_for_tests,
    ENV_PROJECT_STAGING,
)
from .asset_provenance_tracker import (
    ProvenanceRecord,
    AssetProvenanceTracker,
    compute_file_checksum,
    get_asset_provenance_tracker,
    reset_asset_provenance_tracker_for_tests,
)
from .acquisition_pipeline import (
    AcquisitionPipelineResult,
    AcquisitionPipeline,
    get_acquisition_pipeline,
    reset_acquisition_pipeline_for_tests,
)
from .download_review import (
    DownloadReviewResult,
    DownloadReview,
    get_download_review,
    reset_download_review_for_tests,
)
from .download_statistics import (
    DownloadRecord,
    DownloadStatistics,
    get_download_statistics,
    reset_download_statistics_for_tests,
)
from .quixel_bridge_client import (
    BridgeExportResult,
    QuixelBridgeClient,
    get_quixel_bridge_client,
    reset_quixel_bridge_client_for_tests,
)
from .fab_socket_receiver import (
    FabReceivedAsset,
    FabSocketReceiver,
    get_fab_socket_receiver,
    reset_fab_socket_receiver_for_tests,
)
from .download_serializer import (
    DownloadSerializer,
    get_download_serializer,
    reset_download_serializer_for_tests,
)

__all__ = [
    # Session management
    "ProviderSession", "ProviderSessionManager",
    "get_provider_session_manager", "reset_provider_session_manager_for_tests",
    # Auth
    "AuthToken", "MegascansAuth",
    "get_megascans_auth", "reset_megascans_auth_for_tests",
    "ENV_MEGASCANS_TOKEN", "ENV_MEGASCANS_APP_ID",
    "ENV_MEGASCANS_APP_KEY", "ENV_MEGASCANS_USERNAME", "ENV_MEGASCANS_PASSWORD",
    # Search
    "MegascansSearchRecord", "MegascansSearch",
    "get_megascans_search", "reset_megascans_search_for_tests",
    # Download
    "DownloadResult", "MegascansDownloader",
    "get_megascans_downloader", "reset_megascans_downloader_for_tests",
    # Fetcher
    "FetchResult", "AssetFetcher",
    "get_asset_fetcher", "reset_asset_fetcher_for_tests",
    # Queue
    "DownloadTask", "DownloadQueue",
    "get_download_queue", "reset_download_queue_for_tests",
    # Scheduler
    "SchedulerResult", "DownloadScheduler",
    "get_download_scheduler", "reset_download_scheduler_for_tests",
    # Cache
    "CacheEntry", "AssetCacheManager",
    "get_asset_cache_manager", "reset_asset_cache_manager_for_tests",
    "ENV_ASSET_CACHE",
    # Staging
    "StagingEntry", "ProjectAssetStaging",
    "get_project_asset_staging", "reset_project_asset_staging_for_tests",
    "ENV_PROJECT_STAGING",
    # Provenance
    "ProvenanceRecord", "AssetProvenanceTracker",
    "compute_file_checksum",
    "get_asset_provenance_tracker", "reset_asset_provenance_tracker_for_tests",
    # Pipeline
    "AcquisitionPipelineResult", "AcquisitionPipeline",
    "get_acquisition_pipeline", "reset_acquisition_pipeline_for_tests",
    # Review
    "DownloadReviewResult", "DownloadReview",
    "get_download_review", "reset_download_review_for_tests",
    # Statistics
    "DownloadRecord", "DownloadStatistics",
    "get_download_statistics", "reset_download_statistics_for_tests",
    # Bridge / Fab Plugin
    "BridgeExportResult", "QuixelBridgeClient",
    "get_quixel_bridge_client", "reset_quixel_bridge_client_for_tests",
    "FabReceivedAsset", "FabSocketReceiver",
    "get_fab_socket_receiver", "reset_fab_socket_receiver_for_tests",
    # Serializer
    "DownloadSerializer",
    "get_download_serializer", "reset_download_serializer_for_tests",
]
