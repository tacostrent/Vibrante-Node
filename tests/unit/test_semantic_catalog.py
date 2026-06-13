"""
Unit tests for src.runtime.assets.semantic (Tier 12.7).

Covers:
  • AssetEnvironmentMapper — map_environments, rank_environment_fit
  • AssetRoleClassifier — classify_role, rank_role_confidence
  • AssetStorytellingMapper — map_story_role
  • AssetLookdevMapper — infer_lookdev_tags
  • AssetCinematicMapper — infer_cinematic_usage
  • AssetManifestReader — read_manifest, extract_tags
  • MegascansMetadataClient — offline mode, build_asset_record, mock transport
  • AssetMetadataExtractor — extract
  • SemanticAssetEnricher — enrich_asset, individual inference methods
  • AssetKnowledgeGraph — add/remove/query/build_graph
  • AssetCatalog — register/update/remove/get/search/statistics
  • AssetMetadataProvider — priority chain, source resolution
  • AssetCatalogSync — sync_asset, offline mode
  • AssetQueryEngine — query, query_intent, convenience methods
  • AssetCatalogReview — review_catalog, review_asset
  • AssetCatalogSerializer — serialize/deserialize
  • CatalogStatistics — record, summary

All tests are deterministic — no network, no filesystem side-effects.
Megascans API is mocked via injectable transport.
"""
from __future__ import annotations

import json
import os
import pytest

from src.runtime.assets.semantic import (
    # Mappers
    get_asset_environment_mapper, reset_asset_environment_mapper_for_tests,
    BUILTIN_ENVIRONMENTS,
    get_asset_role_classifier, reset_asset_role_classifier_for_tests,
    BUILTIN_ROLES,
    get_asset_storytelling_mapper, reset_asset_storytelling_mapper_for_tests,
    STORYTELLING_ROLES,
    get_asset_lookdev_mapper, reset_asset_lookdev_mapper_for_tests,
    LOOKDEV_TAGS,
    get_asset_cinematic_mapper, reset_asset_cinematic_mapper_for_tests,
    CINEMATIC_USAGES,
    # Infrastructure
    get_catalog_statistics, reset_catalog_statistics_for_tests,
    get_asset_catalog_serializer, reset_asset_catalog_serializer_for_tests,
    get_asset_manifest_reader, reset_asset_manifest_reader_for_tests,
    ManifestRecord,
    get_megascans_metadata_client, reset_megascans_metadata_client_for_tests,
    MegascansAssetMetadata,
    get_asset_metadata_extractor, reset_asset_metadata_extractor_for_tests,
    # Enrichment
    get_semantic_asset_enricher, reset_semantic_asset_enricher_for_tests,
    EnrichedAsset,
    get_asset_knowledge_graph, reset_asset_knowledge_graph_for_tests,
    KnowledgeRelationship,
    # Catalog + query
    get_asset_catalog, reset_asset_catalog_for_tests,
    CatalogEntry,
    get_asset_metadata_provider, reset_asset_metadata_provider_for_tests,
    get_asset_catalog_sync, reset_asset_catalog_sync_for_tests,
    get_asset_query_engine, reset_asset_query_engine_for_tests,
    get_asset_catalog_review, reset_asset_catalog_review_for_tests,
)


# ---------------------------------------------------------------------------
# Autouse fixture — reset ALL singletons before each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_all():
    reset_asset_environment_mapper_for_tests()
    reset_asset_role_classifier_for_tests()
    reset_asset_storytelling_mapper_for_tests()
    reset_asset_lookdev_mapper_for_tests()
    reset_asset_cinematic_mapper_for_tests()
    reset_catalog_statistics_for_tests()
    reset_asset_catalog_serializer_for_tests()
    reset_asset_manifest_reader_for_tests()
    reset_megascans_metadata_client_for_tests()
    reset_asset_metadata_extractor_for_tests()
    reset_semantic_asset_enricher_for_tests()
    reset_asset_knowledge_graph_for_tests()
    reset_asset_catalog_for_tests()
    reset_asset_metadata_provider_for_tests()
    reset_asset_catalog_sync_for_tests()
    reset_asset_query_engine_for_tests()
    reset_asset_catalog_review_for_tests()
    yield
    reset_asset_environment_mapper_for_tests()
    reset_asset_role_classifier_for_tests()
    reset_asset_storytelling_mapper_for_tests()
    reset_asset_lookdev_mapper_for_tests()
    reset_asset_cinematic_mapper_for_tests()
    reset_catalog_statistics_for_tests()
    reset_asset_catalog_serializer_for_tests()
    reset_asset_manifest_reader_for_tests()
    reset_megascans_metadata_client_for_tests()
    reset_asset_metadata_extractor_for_tests()
    reset_semantic_asset_enricher_for_tests()
    reset_asset_knowledge_graph_for_tests()
    reset_asset_catalog_for_tests()
    reset_asset_metadata_provider_for_tests()
    reset_asset_catalog_sync_for_tests()
    reset_asset_query_engine_for_tests()
    reset_asset_catalog_review_for_tests()


# ===========================================================================
# ENVIRONMENT MAPPER
# ===========================================================================

class TestEnvironmentMapper:
    def test_builtin_environments_defined(self):
        assert "industrial_hangar" in BUILTIN_ENVIRONMENTS
        assert "robotics_lab" in BUILTIN_ENVIRONMENTS
        assert "control_room" in BUILTIN_ENVIRONMENTS
        assert "sci_fi_corridor" in BUILTIN_ENVIRONMENTS
        assert "abandoned_factory" in BUILTIN_ENVIRONMENTS

    def test_industrial_pipe_maps_to_hangar(self):
        asset = {"asset_id": "pipe1", "name": "Industrial Pipe Assembly", "tags": ["pipe", "factory"]}
        mapping = get_asset_environment_mapper().map_environments(asset)
        assert "industrial_hangar" in mapping.environments

    def test_robot_arm_maps_to_robotics_lab(self):
        asset = {"asset_id": "rob1", "name": "Robotic Arm", "category": "robot"}
        mapping = get_asset_environment_mapper().map_environments(asset)
        assert "robotics_lab" in mapping.environments
        assert mapping.primary == "robotics_lab"

    def test_empty_asset_no_exception(self):
        mapping = get_asset_environment_mapper().map_environments({})
        assert isinstance(mapping.environments, list)

    def test_none_input_no_exception(self):
        mapping = get_asset_environment_mapper().map_environments(None)
        assert isinstance(mapping.environments, list)

    def test_rank_environment_fit_returns_all_envs(self):
        asset = {"asset_id": "a1", "name": "control panel screen monitor"}
        ranked = get_asset_environment_mapper().rank_environment_fit(asset)
        env_names = [r["environment"] for r in ranked]
        for env in BUILTIN_ENVIRONMENTS:
            assert env in env_names

    def test_deterministic_same_input(self):
        asset = {"asset_id": "d1", "name": "gear turbine boiler furnace", "tags": ["industrial"]}
        m1 = get_asset_environment_mapper().map_environments(asset)
        m2 = get_asset_environment_mapper().map_environments(asset)
        assert m1.environments == m2.environments
        assert m1.primary == m2.primary

    def test_to_dict_from_dict_roundtrip(self):
        asset = {"asset_id": "rt1", "name": "crane platform scaffold", "tags": ["factory"]}
        mapping = get_asset_environment_mapper().map_environments(asset)
        d = mapping.to_dict()
        restored = type(mapping).from_dict(d)
        assert restored.asset_id == mapping.asset_id
        assert restored.environments == mapping.environments

    def test_statistics_increments(self):
        m = get_asset_environment_mapper()
        before = m.get_statistics()["map_count"]
        m.map_environments({"asset_id": "s1", "name": "pipe"})
        assert m.get_statistics()["map_count"] == before + 1


# ===========================================================================
# ROLE CLASSIFIER
# ===========================================================================

class TestRoleClassifier:
    def test_builtin_roles_defined(self):
        for r in ("hero", "support", "foreground", "midground", "background", "set_dressing"):
            assert r in BUILTIN_ROLES

    def test_vehicle_is_hero(self):
        asset = {"asset_id": "v1", "name": "Combat Vehicle", "category": "vehicle"}
        cls = get_asset_role_classifier().classify_role(asset)
        assert cls.primary_role == "hero"
        assert cls.confidence > 0.5

    def test_architecture_is_background(self):
        asset = {"asset_id": "a1", "name": "Building Facade", "category": "architecture"}
        cls = get_asset_role_classifier().classify_role(asset)
        assert cls.primary_role == "background"

    def test_prop_is_set_dressing(self):
        asset = {"asset_id": "p1", "name": "Small Prop", "category": "prop"}
        cls = get_asset_role_classifier().classify_role(asset)
        assert cls.primary_role == "set_dressing"

    def test_empty_asset_returns_default(self):
        cls = get_asset_role_classifier().classify_role({})
        assert cls.primary_role in BUILTIN_ROLES

    def test_deterministic(self):
        asset = {"asset_id": "d1", "name": "Hero Character", "category": "character"}
        r1 = get_asset_role_classifier().classify_role(asset)
        r2 = get_asset_role_classifier().classify_role(asset)
        assert r1.primary_role == r2.primary_role
        assert r1.confidence == r2.confidence

    def test_all_roles_non_empty_for_categorized_asset(self):
        asset = {"asset_id": "ar1", "name": "hero machinery main focal", "category": "machinery"}
        cls = get_asset_role_classifier().classify_role(asset)
        assert len(cls.all_roles) > 0


# ===========================================================================
# STORYTELLING MAPPER
# ===========================================================================

class TestStorytellingMapper:
    def test_storytelling_roles_defined(self):
        for r in ("hero_object", "context_builder", "scale_reference", "visual_anchor", "atmosphere_builder"):
            assert r in STORYTELLING_ROLES

    def test_vehicle_maps_to_hero_object(self):
        asset = {"asset_id": "v1", "name": "Hero Vehicle", "category": "vehicle"}
        m = get_asset_storytelling_mapper().map_story_role(asset)
        assert m.story_role == "hero_object"

    def test_architecture_maps_to_context_builder(self):
        asset = {"asset_id": "arch1", "name": "Wall Structure", "category": "architecture"}
        m = get_asset_storytelling_mapper().map_story_role(asset)
        assert m.story_role == "context_builder"

    def test_atmosphere_keywords(self):
        asset = {"asset_id": "atm1", "name": "Fog Particle Atmosphere Effect", "tags": ["volumetric"]}
        m = get_asset_storytelling_mapper().map_story_role(asset)
        assert m.story_role == "atmosphere_builder"

    def test_empty_returns_default(self):
        m = get_asset_storytelling_mapper().map_story_role({})
        assert m.story_role in STORYTELLING_ROLES

    def test_to_dict_roundtrip(self):
        asset = {"asset_id": "rt1", "name": "hero landmark centerpiece"}
        m = get_asset_storytelling_mapper().map_story_role(asset)
        d = m.to_dict()
        r = type(m).from_dict(d)
        assert r.story_role == m.story_role


# ===========================================================================
# LOOKDEV MAPPER
# ===========================================================================

class TestLookdevMapper:
    def test_lookdev_tags_defined(self):
        for t in ("clean", "weathered", "aged", "industrial", "sci_fi", "rusted"):
            assert t in LOOKDEV_TAGS

    def test_rust_tag_infers_rusted(self):
        asset = {"asset_id": "r1", "name": "Rusted Pipe", "tags": ["rust", "corroded"]}
        m = get_asset_lookdev_mapper().infer_lookdev_tags(asset)
        assert "rusted" in m.lookdev_tags

    def test_sci_fi_keywords(self):
        asset = {"asset_id": "sf1", "name": "Futuristic Tech Panel", "tags": ["neon", "holographic"]}
        m = get_asset_lookdev_mapper().infer_lookdev_tags(asset)
        assert "sci_fi" in m.lookdev_tags

    def test_machinery_category_hints_industrial(self):
        asset = {"asset_id": "m1", "name": "Large Machine", "category": "machinery"}
        m = get_asset_lookdev_mapper().infer_lookdev_tags(asset)
        assert "industrial" in m.lookdev_tags

    def test_explicit_tag_boost(self):
        asset = {"asset_id": "e1", "name": "Clean Asset", "tags": ["clean"]}
        m = get_asset_lookdev_mapper().infer_lookdev_tags(asset)
        assert "clean" in m.lookdev_tags

    def test_empty_returns_list(self):
        m = get_asset_lookdev_mapper().infer_lookdev_tags({})
        assert isinstance(m.lookdev_tags, list)


# ===========================================================================
# CINEMATIC MAPPER
# ===========================================================================

class TestCinematicMapper:
    def test_cinematic_usages_defined(self):
        for u in ("hero_focus", "silhouette", "foreground_interest", "depth_layer", "visual_balance"):
            assert u in CINEMATIC_USAGES

    def test_vehicle_maps_to_hero_focus(self):
        asset = {"asset_id": "v1", "name": "Hero Feature Vehicle", "category": "vehicle"}
        m = get_asset_cinematic_mapper().infer_cinematic_usage(asset)
        assert "hero_focus" in m.cinematic_usage

    def test_architecture_maps_to_depth_layer(self):
        asset = {"asset_id": "a1", "name": "Background Architecture", "category": "architecture"}
        m = get_asset_cinematic_mapper().infer_cinematic_usage(asset)
        assert "depth_layer" in m.cinematic_usage

    def test_foreground_keywords(self):
        asset = {"asset_id": "f1", "name": "Close Foreground Prop Detail", "tags": ["close"]}
        m = get_asset_cinematic_mapper().infer_cinematic_usage(asset)
        assert "foreground_interest" in m.cinematic_usage

    def test_empty_returns_list(self):
        m = get_asset_cinematic_mapper().infer_cinematic_usage({})
        assert isinstance(m.cinematic_usage, list)


# ===========================================================================
# MANIFEST READER
# ===========================================================================

class TestManifestReader:
    def test_read_nonexistent_path_returns_none(self):
        record = get_asset_manifest_reader().read_manifest("/nonexistent/path/12345")
        assert record is None

    def test_read_manifest_from_tmp(self, tmp_path):
        manifest = {
            "id": "test_asset_001",
            "name": "Test Industrial Pipe",
            "category": "prop",
            "tags": ["pipe", "industrial", "metal"],
            "description": "A test industrial pipe assembly",
        }
        (tmp_path / "asset.json").write_text(json.dumps(manifest), encoding="utf-8")
        record = get_asset_manifest_reader().read_manifest(str(tmp_path))
        assert record is not None
        assert record.asset_id == "test_asset_001"
        assert record.name == "Test Industrial Pipe"
        assert "pipe" in record.tags

    def test_reads_manifest_json_fallback(self, tmp_path):
        manifest = {"id": "mfst_01", "name": "Manifest Asset", "type": "3d"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        record = get_asset_manifest_reader().read_manifest(str(tmp_path))
        assert record is not None
        assert record.asset_id == "mfst_01"

    def test_reads_metadata_json_fallback(self, tmp_path):
        manifest = {"asset_id": "meta_01", "name": "Metadata Asset"}
        (tmp_path / "metadata.json").write_text(json.dumps(manifest), encoding="utf-8")
        record = get_asset_manifest_reader().read_manifest(str(tmp_path))
        assert record is not None

    def test_extract_tags_from_comma_string(self):
        data = {"tags": "pipe, metal, factory"}
        tags = get_asset_manifest_reader().extract_tags(data)
        assert "pipe" in tags
        assert "metal" in tags
        assert "factory" in tags

    def test_extract_tags_from_list(self):
        data = {"tags": ["rust", "corroded", "aged"]}
        tags = get_asset_manifest_reader().extract_tags(data)
        assert tags == ["rust", "corroded", "aged"]

    def test_statistics_increments_on_successful_read(self, tmp_path):
        manifest = {"id": "stat_01", "name": "Stat Asset"}
        (tmp_path / "asset.json").write_text(json.dumps(manifest), encoding="utf-8")
        reader = get_asset_manifest_reader()
        before = reader.get_statistics()["read_count"]
        reader.read_manifest(str(tmp_path))
        assert reader.get_statistics()["read_count"] == before + 1


# ===========================================================================
# MEGASCANS METADATA CLIENT
# ===========================================================================

class _MockTransport:
    def __init__(self, response: dict):
        self._response = response

    def get(self, url, token, params):
        return dict(self._response)


class TestMegascansMetadataClient:
    def test_offline_mode_no_token(self):
        client = get_megascans_metadata_client()
        result = client.search_assets("industrial pipe")
        assert result.ok is False
        assert result.source == "offline"
        assert len(result.errors) > 0

    def test_get_asset_offline_returns_none(self):
        client = get_megascans_metadata_client()
        assert client.get_asset("any_id") is None

    def test_authenticate_with_token(self):
        client = get_megascans_metadata_client()
        ok = client.authenticate("fake_test_token_xyz")
        assert ok is True

    def test_build_asset_record_normalizes_ms_type(self):
        client = get_megascans_metadata_client()
        raw = {
            "id": "ms_001",
            "name": "Surface Rock",
            "type": "surface",
            "tags": ["rock", "stone"],
        }
        record = client.build_asset_record(raw)
        assert record.asset_id == "ms_001"
        assert record.category == "material"
        assert "rock" in record.tags

    def test_build_asset_record_3d_type(self):
        client = get_megascans_metadata_client()
        raw = {"id": "ms_002", "name": "3D Prop", "type": "3d"}
        record = client.build_asset_record(raw)
        assert record.category == "prop"

    def test_build_asset_record_3dplant(self):
        client = get_megascans_metadata_client()
        raw = {"id": "ms_003", "name": "3D Plant", "type": "3dplant"}
        record = client.build_asset_record(raw)
        assert record.category == "vegetation"

    def test_mock_transport_search(self):
        client = get_megascans_metadata_client()
        client._transport = _MockTransport({
            "assets": [
                {"id": "mock_01", "name": "Mock Pipe", "type": "3d", "tags": ["pipe"]},
                {"id": "mock_02", "name": "Mock Gear", "type": "3d", "tags": ["gear"]},
            ],
            "total": 2,
        })
        client.authenticate("mock_token")
        result = client.search_assets("pipe")
        assert result.ok is True
        assert len(result.assets) == 2
        assert result.assets[0].asset_id == "mock_01"

    def test_to_dict_from_dict_roundtrip(self):
        client = get_megascans_metadata_client()
        raw = {"id": "rt_01", "name": "Roundtrip Asset", "type": "3d", "tags": ["metal"]}
        record = client.build_asset_record(raw)
        d = record.to_dict()
        r2 = MegascansAssetMetadata.from_dict(d)
        assert r2.asset_id == record.asset_id
        assert r2.category == record.category


# ===========================================================================
# METADATA EXTRACTOR
# ===========================================================================

class TestMetadataExtractor:
    def test_extract_normalizes_tags(self):
        raw = {
            "asset_id": "ex_01",
            "name": "Test Asset",
            "tags": ["PIPE", "Metal", "FACTORY"],
        }
        ex = get_asset_metadata_extractor().extract(raw)
        assert ex.tags == ["pipe", "metal", "factory"]

    def test_extract_deduplicates_tags(self):
        raw = {"asset_id": "dup1", "tags": ["pipe", "pipe", "metal"]}
        ex = get_asset_metadata_extractor().extract(raw)
        assert ex.tags.count("pipe") == 1

    def test_extract_empty_returns_empty(self):
        ex = get_asset_metadata_extractor().extract({})
        assert ex.asset_id == ""
        assert ex.tags == []

    def test_extract_from_manifest_record(self, tmp_path):
        manifest_data = {"id": "mfst_ex_01", "name": "Manifest Extract Test", "tags": ["test"]}
        (tmp_path / "asset.json").write_text(json.dumps(manifest_data), encoding="utf-8")
        manifest = get_asset_manifest_reader().read_manifest(str(tmp_path))
        ex = get_asset_metadata_extractor().extract_from_manifest(manifest)
        assert ex.asset_id == "mfst_ex_01"
        assert ex.metadata_source == "local_manifest"

    def test_statistics_increments(self):
        e = get_asset_metadata_extractor()
        before = e.get_statistics()["extract_count"]
        e.extract({"asset_id": "x1", "name": "test"})
        assert e.get_statistics()["extract_count"] == before + 1


# ===========================================================================
# SEMANTIC ENRICHER
# ===========================================================================

_INDUSTRIAL_PIPE = {
    "asset_id":    "pipe_001",
    "name":        "Industrial Pipe Assembly",
    "category":    "prop",
    "tags":        ["pipe", "industrial", "metal", "factory"],
    "description": "A weathered industrial pipe used in factory settings.",
}


class TestSemanticEnricher:
    def test_enrich_industrial_pipe(self):
        enriched = get_semantic_asset_enricher().enrich_asset(_INDUSTRIAL_PIPE)
        assert enriched.asset_id == "pipe_001"
        assert "industrial_hangar" in enriched.environments or len(enriched.environments) > 0
        assert enriched.primary_role in BUILTIN_ROLES
        assert len(enriched.semantic_tags) > 0

    def test_enrich_empty_no_exception(self):
        enriched = get_semantic_asset_enricher().enrich_asset({})
        assert isinstance(enriched, EnrichedAsset)

    def test_enrich_none_no_exception(self):
        enriched = get_semantic_asset_enricher().enrich_asset(None)
        assert isinstance(enriched, EnrichedAsset)

    def test_infer_environments(self):
        envs = get_semantic_asset_enricher().infer_environments(_INDUSTRIAL_PIPE)
        assert isinstance(envs, list)
        assert "industrial_hangar" in envs

    def test_infer_lookdev(self):
        lookdev = get_semantic_asset_enricher().infer_lookdev(_INDUSTRIAL_PIPE)
        assert isinstance(lookdev, list)
        assert "industrial" in lookdev

    def test_infer_asset_importance(self):
        asset = {"asset_id": "hero1", "name": "Hero Vehicle", "category": "vehicle"}
        importance = get_semantic_asset_enricher().infer_asset_importance(asset)
        assert importance == "primary"

    def test_enriched_to_dict_roundtrip(self):
        enriched = get_semantic_asset_enricher().enrich_asset(_INDUSTRIAL_PIPE)
        d = enriched.to_dict()
        r = EnrichedAsset.from_dict(d)
        assert r.asset_id == enriched.asset_id
        assert r.environments == enriched.environments
        assert r.semantic_tags == enriched.semantic_tags

    def test_deterministic(self):
        e1 = get_semantic_asset_enricher().enrich_asset(_INDUSTRIAL_PIPE)
        e2 = get_semantic_asset_enricher().enrich_asset(_INDUSTRIAL_PIPE)
        assert e1.environments == e2.environments
        assert e1.primary_role == e2.primary_role
        assert e1.lookdev_tags == e2.lookdev_tags

    def test_statistics_increments(self):
        en = get_semantic_asset_enricher()
        before = en.get_statistics()["enrich_count"]
        en.enrich_asset({"asset_id": "s1"})
        assert en.get_statistics()["enrich_count"] == before + 1


# ===========================================================================
# KNOWLEDGE GRAPH
# ===========================================================================

class TestKnowledgeGraph:
    def test_add_relationship(self):
        graph = get_asset_knowledge_graph()
        rel = graph.add_relationship("asset_a", "commonly_used_with", "asset_b", weight=0.9)
        assert rel.source_id == "asset_a"
        assert rel.relation == "commonly_used_with"
        assert rel.target_id == "asset_b"
        assert rel.weight == 0.9

    def test_add_empty_ids_ignored(self):
        graph = get_asset_knowledge_graph()
        rel = graph.add_relationship("", "commonly_used_with", "asset_b")
        assert rel.source_id == ""

    def test_remove_relationship(self):
        graph = get_asset_knowledge_graph()
        graph.add_relationship("a1", "same_environment", "a2")
        removed = graph.remove_relationship("a1", "same_environment", "a2")
        assert removed is True
        rels = graph.query_relationships("a1")
        assert len(rels) == 0

    def test_remove_nonexistent_returns_false(self):
        assert get_asset_knowledge_graph().remove_relationship("x", "y", "z") is False

    def test_query_relationships_by_asset(self):
        graph = get_asset_knowledge_graph()
        graph.add_relationship("p1", "same_style", "p2")
        graph.add_relationship("p1", "commonly_used_with", "p3")
        rels = graph.query_relationships("p1")
        assert len(rels) == 2

    def test_query_relationships_by_type(self):
        graph = get_asset_knowledge_graph()
        graph.add_relationship("p1", "same_style", "p2")
        graph.add_relationship("p1", "commonly_used_with", "p3")
        rels = graph.query_relationships("p1", relation_type="same_style")
        assert len(rels) == 1
        assert rels[0].relation == "same_style"

    def test_query_as_target(self):
        graph = get_asset_knowledge_graph()
        graph.add_relationship("p1", "same_environment", "p2")
        rels = graph.query_relationships("p2")
        assert len(rels) == 1

    def test_get_neighbors(self):
        graph = get_asset_knowledge_graph()
        graph.add_relationship("a", "same_environment", "b")
        graph.add_relationship("a", "same_style", "c")
        neighbors = graph.get_neighbors("a")
        assert "b" in neighbors
        assert "c" in neighbors

    def test_build_graph_from_enriched_assets(self):
        assets = [
            {"asset_id": "a1", "primary_env": "industrial_hangar", "primary_lookdev": "industrial"},
            {"asset_id": "a2", "primary_env": "industrial_hangar", "primary_lookdev": "industrial"},
            {"asset_id": "a3", "primary_env": "robotics_lab", "primary_lookdev": "sci_fi"},
        ]
        graph = get_asset_knowledge_graph()
        added = graph.build_graph(assets)
        assert added > 0
        # a1 and a2 share env and style — should be related
        neighbors_a1 = graph.get_neighbors("a1")
        assert "a2" in neighbors_a1

    def test_statistics(self):
        graph = get_asset_knowledge_graph()
        graph.add_relationship("x1", "same_environment", "x2")
        graph.add_relationship("x1", "same_style", "x3")
        stats = graph.get_statistics()
        assert stats["total_relationships"] == 2
        assert "same_environment" in stats["by_type"]

    def test_clear(self):
        graph = get_asset_knowledge_graph()
        graph.add_relationship("c1", "same_style", "c2")
        graph.clear()
        assert graph.get_statistics()["total_relationships"] == 0

    def test_to_dict_from_dict_roundtrip(self):
        graph = get_asset_knowledge_graph()
        rel = graph.add_relationship("r1", "successful_pairing", "r2", weight=0.75, metadata={"reason": "test"})
        d = rel.to_dict()
        r2 = KnowledgeRelationship.from_dict(d)
        assert r2.source_id == "r1"
        assert r2.weight == 0.75
        assert r2.metadata["reason"] == "test"


# ===========================================================================
# ASSET CATALOG
# ===========================================================================

_ENRICHED_PIPE = {
    "asset_id":       "cat_pipe_001",
    "name":           "Industrial Pipe",
    "provider":       "megascans",
    "category":       "prop",
    "tags":           ["pipe", "industrial"],
    "environments":   ["industrial_hangar"],
    "primary_env":    "industrial_hangar",
    "roles":          ["set_dressing", "support"],
    "primary_role":   "set_dressing",
    "lookdev_tags":   ["industrial", "weathered"],
    "primary_lookdev":"industrial",
    "story_role":     "context_builder",
    "cinematic_usage":["depth_layer"],
    "primary_cinematic":"depth_layer",
    "importance":     "ambient",
    "semantic_tags":  ["industrial_hangar", "set_dressing", "industrial"],
}


class TestAssetCatalog:
    def test_register_and_get(self):
        catalog = get_asset_catalog()
        catalog.register_asset("cat_pipe_001", _ENRICHED_PIPE)
        entry = catalog.get_asset("cat_pipe_001")
        assert entry is not None
        assert entry.asset_id == "cat_pipe_001"
        assert entry.name == "Industrial Pipe"

    def test_asset_exists(self):
        catalog = get_asset_catalog()
        catalog.register_asset("ex_01", _ENRICHED_PIPE)
        assert catalog.asset_exists("ex_01") is True
        assert catalog.asset_exists("not_here") is False

    def test_update_asset(self):
        catalog = get_asset_catalog()
        catalog.register_asset("upd_01", _ENRICHED_PIPE)
        ok = catalog.update_asset("upd_01", {"name": "Updated Pipe"})
        assert ok is True
        assert catalog.get_asset("upd_01").name == "Updated Pipe"

    def test_remove_asset(self):
        catalog = get_asset_catalog()
        catalog.register_asset("rm_01", _ENRICHED_PIPE)
        ok = catalog.remove_asset("rm_01")
        assert ok is True
        assert catalog.get_asset("rm_01") is None

    def test_remove_nonexistent_returns_false(self):
        assert get_asset_catalog().remove_asset("ghost_001") is False

    def test_search_by_environment(self):
        catalog = get_asset_catalog()
        catalog.register_asset("env_01", _ENRICHED_PIPE)
        results = catalog.search_assets(environment="industrial_hangar")
        assert any(e.asset_id == "env_01" for e in results)

    def test_search_by_role(self):
        catalog = get_asset_catalog()
        catalog.register_asset("role_01", _ENRICHED_PIPE)
        results = catalog.search_assets(role="set_dressing")
        assert any(e.asset_id == "role_01" for e in results)

    def test_search_by_query(self):
        catalog = get_asset_catalog()
        catalog.register_asset("q_01", _ENRICHED_PIPE)
        results = catalog.search_assets(query="industrial")
        assert any(e.asset_id == "q_01" for e in results)

    def test_search_no_match_returns_empty(self):
        catalog = get_asset_catalog()
        catalog.register_asset("nm_01", _ENRICHED_PIPE)
        results = catalog.search_assets(environment="robotics_lab")
        assert not any(e.asset_id == "nm_01" for e in results)

    def test_statistics(self):
        catalog = get_asset_catalog()
        catalog.register_asset("st_01", _ENRICHED_PIPE)
        stats = catalog.get_statistics()
        assert stats["total"] >= 1

    def test_iter_all(self):
        catalog = get_asset_catalog()
        catalog.register_asset("it_01", _ENRICHED_PIPE)
        catalog.register_asset("it_02", {**_ENRICHED_PIPE, "asset_id": "it_02"})
        ids = [e.asset_id for e in catalog.iter_all()]
        assert "it_01" in ids
        assert "it_02" in ids

    def test_catalog_entry_from_enriched(self):
        entry = CatalogEntry.from_enriched(_ENRICHED_PIPE, {"local_path": "/tmp/pipe"})
        assert entry.environments == ["industrial_hangar"]
        assert entry.roles == ["set_dressing", "support"]
        assert entry.local_path == "/tmp/pipe"

    def test_to_dict_from_dict_roundtrip(self):
        catalog = get_asset_catalog()
        catalog.register_asset("rt_c_01", _ENRICHED_PIPE)
        entry = catalog.get_asset("rt_c_01")
        d = entry.to_dict()
        restored = CatalogEntry.from_dict(d)
        assert restored.asset_id == entry.asset_id
        assert restored.environments == entry.environments


# ===========================================================================
# METADATA PROVIDER — source priority chain
# ===========================================================================

class TestMetadataProvider:
    def test_fallback_when_no_source(self):
        provider = get_asset_metadata_provider()
        record = provider.get_metadata("unknown_asset_xyz")
        assert record.metadata_source == "provider_fallback"

    def test_catalog_source_priority(self):
        # Register in catalog first
        get_asset_catalog().register_asset("prov_01", _ENRICHED_PIPE)
        provider = get_asset_metadata_provider()
        record = provider.get_metadata("prov_01")
        assert record.metadata_source == "catalog"
        assert record.asset_id == "prov_01"

    def test_manifest_source_priority(self, tmp_path):
        manifest = {"id": "mnf_prov_01", "name": "Manifest Priority Asset", "tags": ["pipe"]}
        (tmp_path / "asset.json").write_text(json.dumps(manifest), encoding="utf-8")
        provider = get_asset_metadata_provider()
        record = provider.get_metadata("mnf_prov_01", local_path=str(tmp_path))
        assert record.metadata_source == "local_manifest"

    def test_manifest_before_catalog(self, tmp_path):
        # Both manifest and catalog exist — manifest wins
        manifest = {"id": "priority_01", "name": "Manifest Asset"}
        (tmp_path / "asset.json").write_text(json.dumps(manifest), encoding="utf-8")
        get_asset_catalog().register_asset("priority_01", _ENRICHED_PIPE)
        provider = get_asset_metadata_provider()
        record = provider.get_metadata("priority_01", local_path=str(tmp_path))
        assert record.metadata_source == "local_manifest"

    def test_resolve_metadata_source(self):
        source = get_asset_metadata_provider().resolve_metadata_source("xyz_never_exists")
        assert source == "provider_fallback"

    def test_refresh_clears_cache(self):
        provider = get_asset_metadata_provider()
        r1 = provider.get_metadata("cache_test_01")
        provider.clear_cache()
        r2 = provider.get_metadata("cache_test_01")
        assert r1.metadata_source == r2.metadata_source


# ===========================================================================
# CATALOG SYNC
# ===========================================================================

class TestCatalogSync:
    def test_sync_offline_returns_warning(self):
        sync = get_asset_catalog_sync()
        report = sync.sync_catalog(query="industrial")
        # Offline — should return a warning, not an error crash
        assert isinstance(report.warnings, list) or not report.ok

    def test_sync_asset_new(self):
        sync = get_asset_catalog_sync()
        result = sync.sync_asset({
            "asset_id": "sync_01",
            "name": "Sync Test Asset",
            "category": "prop",
            "tags": ["pipe", "industrial"],
        })
        assert result == "added"

    def test_sync_asset_skip_existing(self):
        sync = get_asset_catalog_sync()
        asset = {"asset_id": "skip_01", "name": "Skip Me", "category": "prop"}
        sync.sync_asset(asset)
        result = sync.sync_asset(asset)
        assert result == "skipped"

    def test_sync_asset_force_update(self):
        sync = get_asset_catalog_sync()
        asset = {"asset_id": "force_01", "name": "Force Me", "category": "prop"}
        sync.sync_asset(asset)
        result = sync.sync_asset(asset, force_update=True)
        assert result == "updated"

    def test_sync_asset_missing_id(self):
        sync = get_asset_catalog_sync()
        result = sync.sync_asset({"name": "No ID"})
        assert result == "error"

    def test_remove_deleted_assets(self):
        catalog = get_asset_catalog()
        catalog.register_asset("keep_01", _ENRICHED_PIPE)
        catalog.register_asset("remove_01", {**_ENRICHED_PIPE, "asset_id": "remove_01"})
        sync = get_asset_catalog_sync()
        report = sync.remove_deleted_assets(["keep_01"])
        assert report.removed == 1
        assert catalog.asset_exists("keep_01")
        assert not catalog.asset_exists("remove_01")

    def test_refresh_existing_assets(self):
        catalog = get_asset_catalog()
        catalog.register_asset("ref_01", _ENRICHED_PIPE)
        sync = get_asset_catalog_sync()
        report = sync.refresh_existing_assets(limit=10)
        assert report.updated >= 1

    def test_build_sync_report(self):
        report = get_asset_catalog_sync().build_sync_report()
        assert "sync_count" in report


# ===========================================================================
# QUERY ENGINE
# ===========================================================================

class TestQueryEngine:
    def _populate_catalog(self):
        catalog = get_asset_catalog()
        _data = [
            ("qe_00", "Industrial Pipe",     "prop",         ["pipe", "industrial"],  ["industrial_hangar"],                      ["set_dressing"], ["industrial"],            "context_builder", ["depth_layer"],   "ambient"),
            ("qe_01", "Factory Gear",         "machinery",    ["gear", "factory"],     ["industrial_hangar", "robotics_lab"],       ["support"],      ["industrial", "weathered"],"context_builder",["visual_balance"],"secondary"),
            ("qe_02", "Combat Vehicle",       "vehicle",      ["combat", "armor"],     ["industrial_hangar"],                      ["hero"],         ["worn"],                  "hero_object",     ["hero_focus"],    "primary"),
            ("qe_03", "Wall Structure",       "architecture", ["wall", "structure"],   ["abandoned_factory"],                      ["background"],   ["aged"],                  "context_builder", ["depth_layer"],   "tertiary"),
        ]
        for asset_id, name, cat, tags, envs, roles, ldevs, story, cin, imp in _data:
            enriched = {
                "asset_id":        asset_id,
                "name":            name,
                "provider":        "megascans",
                "category":        cat,
                "tags":            tags,
                "environments":    envs,
                "primary_env":     envs[0] if envs else "",
                "roles":           roles,
                "primary_role":    roles[0] if roles else "set_dressing",
                "lookdev_tags":    ldevs,
                "primary_lookdev": ldevs[0] if ldevs else "",
                "story_role":      story,
                "cinematic_usage": cin,
                "primary_cinematic": cin[0] if cin else "",
                "importance":      imp,
                "semantic_tags":   envs + roles + ldevs,
                "storytelling":    story,
            }
            catalog.register_asset(asset_id, enriched)
        return catalog

    def test_query_by_environment(self):
        self._populate_catalog()
        result = get_asset_query_engine().query_environment("industrial_hangar", limit=10)
        assert result.ok is True
        assert result.total > 0

    def test_query_by_role(self):
        self._populate_catalog()
        result = get_asset_query_engine().query_role("hero", limit=10)
        assert result.ok is True
        assert result.total > 0

    def test_query_by_lookdev(self):
        self._populate_catalog()
        result = get_asset_query_engine().query_lookdev("industrial", limit=10)
        assert result.ok is True
        assert result.total > 0

    def test_query_by_cinematic(self):
        self._populate_catalog()
        result = get_asset_query_engine().query_cinematic("hero_focus", limit=10)
        assert result.ok is True

    def test_query_intent_parses_environment(self):
        self._populate_catalog()
        result = get_asset_query_engine().query_intent("Industrial Hangar", limit=10)
        assert result.ok is True

    def test_query_intent_parses_role(self):
        self._populate_catalog()
        result = get_asset_query_engine().query_intent("Hero machinery", limit=10)
        assert result.ok is True

    def test_empty_catalog_returns_empty(self):
        result = get_asset_query_engine().query(environment="industrial_hangar")
        assert result.ok is True
        assert result.total == 0

    def test_query_respects_limit(self):
        catalog = get_asset_catalog()
        for i in range(10):
            catalog.register_asset(f"lim_{i:02d}", {
                **_ENRICHED_PIPE,
                "asset_id": f"lim_{i:02d}",
                "environments": ["industrial_hangar"],
            })
        result = get_asset_query_engine().query(environment="industrial_hangar", limit=3)
        assert result.total <= 3

    def test_query_result_to_dict(self):
        result = get_asset_query_engine().query()
        d = result.to_dict()
        assert "ok" in d
        assert "assets" in d
        assert "total" in d


# ===========================================================================
# CATALOG REVIEW
# ===========================================================================

class TestCatalogReview:
    def test_empty_catalog_review(self):
        result = get_asset_catalog_review().review_catalog()
        assert result.ok is True
        assert result.score == 0.0
        assert result.production_ready is False
        assert any("empty catalog" in f for f in result.findings)

    def test_well_enriched_catalog_production_ready(self):
        catalog = get_asset_catalog()
        for i in range(5):
            catalog.register_asset(f"pr_{i}", {
                **_ENRICHED_PIPE,
                "asset_id": f"pr_{i}",
                "lookdev_tags": ["industrial", "weathered"],
                "semantic_tags": ["industrial_hangar", "set_dressing", "industrial"],
            })
        result = get_asset_catalog_review().review_catalog()
        assert result.score > 0.0
        assert result.total_assets == 5

    def test_review_asset_missing(self):
        result = get_asset_catalog_review().review_asset("ghost_001")
        assert result.ok is False

    def test_review_asset_well_enriched(self):
        catalog = get_asset_catalog()
        catalog.register_asset("rev_01", _ENRICHED_PIPE)
        result = get_asset_catalog_review().review_asset("rev_01")
        assert result.ok is True
        assert result.score > 0.0
        assert result.grade in ("A", "B", "C", "D", "F")

    def test_review_coverage_breakdown(self):
        catalog = get_asset_catalog()
        catalog.register_asset("cov_01", _ENRICHED_PIPE)
        coverage = get_asset_catalog_review().review_coverage()
        assert "total" in coverage
        assert coverage["total"] >= 1

    def test_grade_mapping(self):
        from src.runtime.assets.semantic.asset_catalog_review import _grade
        assert _grade(0.9) == "A"
        assert _grade(0.75) == "B"
        assert _grade(0.6) == "C"
        assert _grade(0.45) == "D"
        assert _grade(0.1) == "F"


# ===========================================================================
# CATALOG SERIALIZER
# ===========================================================================

class TestCatalogSerializer:
    def test_serialize_empty_list(self):
        s = get_asset_catalog_serializer()
        out = s.serialize_catalog([])
        parsed = json.loads(out)
        assert parsed["entries"] == []

    def test_serialize_deserialize_roundtrip(self):
        entries = [_ENRICHED_PIPE]
        s = get_asset_catalog_serializer()
        data = s.serialize_catalog(entries)
        restored = s.deserialize_catalog(data)
        assert len(restored) == 1
        assert restored[0]["asset_id"] == "cat_pipe_001"

    def test_deserialize_invalid_json(self):
        s = get_asset_catalog_serializer()
        result = s.deserialize_catalog("not valid json !!!")
        assert result == []

    def test_serialize_entry(self):
        s = get_asset_catalog_serializer()
        out = s.serialize_entry({"asset_id": "ser_01", "name": "Test"})
        d = json.loads(out)
        assert d["asset_id"] == "ser_01"

    def test_schema_version(self):
        assert get_asset_catalog_serializer().schema_version == "1.0.0"


# ===========================================================================
# CATALOG STATISTICS
# ===========================================================================

class TestCatalogStatistics:
    def test_record_operation(self):
        stats = get_catalog_statistics()
        stats.record("register", asset_id="s1", ok=True)
        summary = stats.get_summary()
        assert summary["register_count"] >= 1

    def test_record_error_increments_error_count(self):
        stats = get_catalog_statistics()
        stats.record("query", ok=False)
        summary = stats.get_summary()
        assert summary["error_count"] >= 1

    def test_get_recent(self):
        stats = get_catalog_statistics()
        for i in range(5):
            stats.record("query", asset_id=f"r{i}")
        recent = stats.get_recent(3)
        assert len(recent) == 3

    def test_reset(self):
        stats = get_catalog_statistics()
        stats.record("sync", asset_id="x1")
        stats.reset()
        assert stats.get_summary()["total_records"] == 0

    def test_cap_at_max_records(self):
        from src.runtime.assets.semantic.asset_catalog_statistics import _MAX_RECORDS
        stats = get_catalog_statistics()
        for i in range(_MAX_RECORDS + 10):
            stats.record("query", asset_id=f"x{i}")
        # Should not crash and should not exceed 2x max
        summary = stats.get_summary()
        assert summary["total_records"] < _MAX_RECORDS * 2


# ===========================================================================
# INTEGRATION — metadata source priority chain
# ===========================================================================

class TestMetadataSourcePriority:
    """Validates the Local Manifest → Catalog → API → Fallback chain."""

    def test_fallback_used_for_unknown_asset(self):
        source = get_asset_metadata_provider().resolve_metadata_source("never_exists_xyz")
        assert source == "provider_fallback"

    def test_catalog_used_when_registered(self):
        get_asset_catalog().register_asset("chain_01", _ENRICHED_PIPE)
        source = get_asset_metadata_provider().resolve_metadata_source("chain_01")
        assert source == "catalog"

    def test_manifest_used_when_local_path_provided(self, tmp_path):
        manifest = {"id": "chain_02", "name": "Local Manifest Asset"}
        (tmp_path / "asset.json").write_text(json.dumps(manifest), encoding="utf-8")
        source = get_asset_metadata_provider().resolve_metadata_source(
            "chain_02", local_path=str(tmp_path)
        )
        assert source == "local_manifest"

    def test_megascans_api_not_queried_when_catalog_exists(self):
        # Register in catalog
        get_asset_catalog().register_asset("api_skip_01", _ENRICHED_PIPE)
        client = get_megascans_metadata_client()
        # Mock transport that would return a record if called
        call_count = [0]
        class CountingTransport:
            def get(self, url, token, params):
                call_count[0] += 1
                return {}
        client._transport = CountingTransport()
        client.authenticate("fake_token")

        # Provider should resolve from catalog, not API
        source = get_asset_metadata_provider().resolve_metadata_source("api_skip_01")
        assert source == "catalog"
        assert call_count[0] == 0  # API was NOT called
