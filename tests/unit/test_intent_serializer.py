"""
Tests for src.runtime.semantic.serialization.intent_serializer
No bridge, no LLM. Pure unit tests.
"""
import json
import os
import tempfile
import pytest
from src.runtime.semantic.serialization.intent_serializer import (
    SchemaVersionError,
    IntentSerializationError,
    IntentSerializer,
    get_intent_serializer,
    reset_intent_serializer_for_tests,
)
from src.runtime.semantic.schema.scene_intent_schema import SceneIntent, SCHEMA_VERSION


@pytest.fixture(autouse=True)
def reset():
    reset_intent_serializer_for_tests()
    yield
    reset_intent_serializer_for_tests()


def _make_intent(**kwargs):
    defaults = dict(
        source_prompt="burning city at night",
        environment="urban",
        confidence=0.85,
    )
    defaults.update(kwargs)
    return SceneIntent(**defaults)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_singleton():
    a = get_intent_serializer()
    b = get_intent_serializer()
    assert a is b


def test_reset_creates_new():
    a = get_intent_serializer()
    reset_intent_serializer_for_tests()
    b = get_intent_serializer()
    assert a is not b


# ---------------------------------------------------------------------------
# to_json / from_json
# ---------------------------------------------------------------------------

def test_to_json_returns_string():
    s = IntentSerializer()
    intent = _make_intent()
    js = s.to_json(intent)
    assert isinstance(js, str)
    assert '"urban"' in js


def test_to_json_compact():
    s = IntentSerializer()
    intent = _make_intent()
    compact = s.to_json(intent, compact=True)
    pretty = s.to_json(intent, compact=False)
    assert len(compact) < len(pretty)
    assert "\n" not in compact


def test_from_json_round_trip():
    s = IntentSerializer()
    intent = _make_intent()
    js = s.to_json(intent)
    intent2 = s.from_json(js)
    assert intent2.environment == "urban"
    assert intent2.confidence == 0.85
    assert intent2.source_prompt == "burning city at night"


def test_from_json_invalid_json():
    s = IntentSerializer()
    with pytest.raises(IntentSerializationError):
        s.from_json("this is not json")


def test_from_json_non_dict():
    s = IntentSerializer()
    with pytest.raises(IntentSerializationError):
        s.from_json("[1, 2, 3]")


def test_from_json_unsupported_version_strict():
    s = IntentSerializer()
    intent = _make_intent()
    d = intent.to_dict()
    d["schema_version"] = "9.9.9"
    js = json.dumps(d)
    with pytest.raises(SchemaVersionError):
        s.from_json(js, lenient=False)


def test_from_json_unsupported_version_lenient():
    s = IntentSerializer()
    intent = _make_intent()
    d = intent.to_dict()
    d["schema_version"] = "9.9.9"
    js = json.dumps(d)
    # lenient=True should not raise
    intent2 = s.from_json(js, lenient=True)
    assert intent2.environment == "urban"


# ---------------------------------------------------------------------------
# save / load (file I/O)
# ---------------------------------------------------------------------------

def test_save_and_load(tmp_path):
    s = IntentSerializer()
    intent = _make_intent()
    path = tmp_path / "intent.json"
    s.save(intent, path)
    assert path.exists()
    intent2 = s.load(path)
    assert intent2.environment == "urban"


def test_load_nonexistent_raises(tmp_path):
    s = IntentSerializer()
    with pytest.raises(FileNotFoundError):
        s.load(tmp_path / "ghost.json")


def test_save_compact(tmp_path):
    s = IntentSerializer()
    intent = _make_intent()
    path = tmp_path / "compact.json"
    s.save(intent, path, compact=True)
    content = path.read_text()
    assert "\n" not in content


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------

def test_to_json_list_and_from():
    s = IntentSerializer()
    intents = [_make_intent(), _make_intent(environment="desert")]
    js = s.to_json_list(intents)
    loaded = s.from_json_list(js)
    assert len(loaded) == 2
    assert loaded[0].environment == "urban"
    assert loaded[1].environment == "desert"


def test_from_json_list_non_list():
    s = IntentSerializer()
    with pytest.raises(IntentSerializationError):
        s.from_json_list('{"not": "a list"}')


def test_save_list_and_load_list(tmp_path):
    s = IntentSerializer()
    intents = [_make_intent(), _make_intent(environment="forest")]
    path = tmp_path / "intents.json"
    s.save_list(intents, path)
    loaded = s.load_list(path)
    assert len(loaded) == 2
    envs = [i.environment for i in loaded]
    assert "urban" in envs
    assert "forest" in envs


def test_from_json_list_item_not_dict():
    s = IntentSerializer()
    with pytest.raises(IntentSerializationError):
        s.from_json_list('[1, 2, 3]')
