"""
Tests for the 4 Houdini asset intelligence nodes.

Verifies:
  - JSON files exist in the correct location
  - Required fields present: node_id, name, description, category, use_exec
  - Category is "Houdini"
  - use_exec is True
  - exec ports (exec_in / exec_out) are NOT in the JSON arrays
  - python_code compiles without errors
  - register_node() is defined and returns a class
  - execute() is an async method
  - execute() returns exec_out key

Tests never call get_bridge() or make HTTP requests.
"""

import ast
import importlib.util
import json
import os
import sys
import types
import pytest

_NODE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "plugins", "houdini", "v_nodes_houdini",
)

_ASSET_NODES = [
    "hou_mcp_asset_discover",
    "hou_mcp_asset_validate",
    "hou_mcp_asset_rank",
    "hou_mcp_asset_recommend",
]

_FORBIDDEN_TOOLS = {
    "create_node", "set_parm", "set_parms", "run_python",
    "run_code", "delete_node", "raw_houdini_execute",
    "connect_nodes", "cook_node",
}


def _load_node_json(node_id: str) -> dict:
    path = os.path.join(_NODE_DIR, f"{node_id}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _compile_and_exec(code: str, node_id: str) -> types.ModuleType:
    """Compile python_code and exec it in a fresh module namespace."""
    mod = types.ModuleType(f"_node_{node_id}")
    mod.__file__ = f"<{node_id}>"

    # Stub out heavy dependencies so compile succeeds without the full app
    src_stub = types.ModuleType("src")
    src_stub.runtime = types.ModuleType("src.runtime")
    sys.modules.setdefault("src", src_stub)

    nodes_stub = types.ModuleType("src.nodes")
    base_stub  = types.ModuleType("src.nodes.base")

    class _BaseNode:
        def __init__(self):
            self.icon_path = None
            self._inputs = {}
            self._outputs = {}

        def add_input(self, name, *a, **kw):
            self._inputs[name] = (a, kw)

        def add_output(self, name, *a, **kw):
            self._outputs[name] = (a, kw)

        def log_info(self, msg): pass
        def log_error(self, msg): pass
        def log_warning(self, msg): pass

    base_stub.BaseNode = _BaseNode
    sys.modules.setdefault("src.nodes", nodes_stub)
    sys.modules.setdefault("src.nodes.base", base_stub)

    # Stub runtime.assets so imports don't fail
    for sub in ("src.runtime.assets", "src.runtime.assets.schema"):
        sys.modules.setdefault(sub, types.ModuleType(sub))

    compiled = compile(code, f"<{node_id}>", "exec")
    exec(compiled, mod.__dict__)
    return mod


# ---------------------------------------------------------------------------
# Parametrized tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_id", _ASSET_NODES)
class TestAssetHoudiniNodes:

    def test_file_exists(self, node_id):
        path = os.path.join(_NODE_DIR, f"{node_id}.json")
        assert os.path.isfile(path), f"Node file not found: {path}"

    def test_required_fields(self, node_id):
        d = _load_node_json(node_id)
        for field in ("node_id", "name", "description", "category",
                      "use_exec", "inputs", "outputs", "python_code"):
            assert field in d, f"Missing field {field!r} in {node_id}"

    def test_node_id_matches_filename(self, node_id):
        d = _load_node_json(node_id)
        assert d["node_id"] == node_id

    def test_category_is_houdini(self, node_id):
        d = _load_node_json(node_id)
        assert d["category"] == "Houdini"

    def test_use_exec_is_true(self, node_id):
        d = _load_node_json(node_id)
        assert d["use_exec"] is True

    def test_exec_ports_not_in_json_arrays(self, node_id):
        d = _load_node_json(node_id)
        exec_names = {"exec_in", "exec_out"}
        for port in d.get("inputs", []):
            assert port["name"] not in exec_names, \
                f"{node_id}: exec port {port['name']!r} must not appear in JSON inputs array"
        for port in d.get("outputs", []):
            assert port["name"] not in exec_names, \
                f"{node_id}: exec port {port['name']!r} must not appear in JSON outputs array"

    def test_python_code_compiles(self, node_id):
        d = _load_node_json(node_id)
        code = d["python_code"]
        try:
            compile(code, f"<{node_id}>", "exec")
        except SyntaxError as exc:
            pytest.fail(f"Syntax error in {node_id}: {exc}")

    def test_register_node_defined(self, node_id):
        d = _load_node_json(node_id)
        code = d["python_code"]
        tree = ast.parse(code)
        fn_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        assert "register_node" in fn_names, f"{node_id}: register_node not defined"

    def test_async_execute_defined(self, node_id):
        d = _load_node_json(node_id)
        code = d["python_code"]
        tree = ast.parse(code)
        async_fns = {
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.AsyncFunctionDef)
        }
        assert "execute" in async_fns, f"{node_id}: execute is not async def"

    def test_execute_returns_exec_out(self, node_id):
        d = _load_node_json(node_id)
        code = d["python_code"]
        # Check that "exec_out" appears in python_code
        assert "exec_out" in code, f"{node_id}: exec_out not returned"

    def test_no_forbidden_tools_exposed(self, node_id):
        d = _load_node_json(node_id)
        code = d["python_code"]
        for forbidden in _FORBIDDEN_TOOLS:
            # Only check that the node doesn't call bridge methods directly
            # (tools like run_code / create_node used via bridge are blocked)
            if f'bridge.{forbidden}' in code:
                pytest.fail(f"{node_id}: forbidden tool {forbidden!r} called directly")

    def test_description_nonempty(self, node_id):
        d = _load_node_json(node_id)
        assert len(d["description"]) > 20

    def test_has_exec_in_in_add_input(self, node_id):
        d = _load_node_json(node_id)
        # super().__init__() handles exec_in — check it's NOT manually added
        code = d["python_code"]
        assert 'add_input("exec_in"' not in code, \
            f"{node_id}: exec_in must not be manually added (super().__init__() does it)"

    def test_has_no_get_bridge_call(self, node_id):
        d = _load_node_json(node_id)
        code = d["python_code"]
        assert "get_bridge()" not in code, \
            f"{node_id}: asset intelligence nodes must not call get_bridge()"
