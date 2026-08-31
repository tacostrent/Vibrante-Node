from src.nodes.base import BaseNode


class GroupInNode(BaseNode):
    """Input boundary marker inside a subgraph.

    The GroupNode sets parameters['_injected_value'] to the external input
    before running the sub-executor.  execute() reads that key (not 'value',
    which is an output port and is wiped by clear_outputs() during engine prep).
    """
    name = "group_in"
    description = "Subgraph input boundary — provides an external value to the internal graph"
    category = "Group"

    def __init__(self):
        super().__init__(use_exec=False)
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("port_name", "string", widget_type="text", default="")
        self.add_output("value", "any")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        return {"value": self.parameters.get("_injected_value")}


class GroupOutNode(BaseNode):
    """Output boundary marker inside a subgraph.

    After the sub-executor finishes, GroupNode reads node_results[id]['value']
    and maps it to the corresponding group output port.

    exec_in/exec_out allow the inner exec chain to route explicitly through this
    node.  When wired, the node runs at the point the exec chain reaches it.
    When not wired (legacy subgraphs), it runs as a data entry node — same
    as before, so existing saved workflows are unaffected.
    """
    name = "group_out"
    description = "Subgraph output boundary — returns a value to the parent graph"
    category = "Group"

    def __init__(self):
        super().__init__(use_exec=True)
        # [AUTO-GENERATED-PORTS-START]
        self.add_input("port_name", "string", widget_type="text", default="")
        self.add_input("value", "any")
        self.add_output("value", "any")
        # [AUTO-GENERATED-PORTS-END]

    async def execute(self, inputs):
        await self.set_output("exec_out", True)
        return {"value": inputs.get("value"), "exec_out": True}


class GroupNode(BaseNode):
    """Collapsed subgraph node.

    Stores a complete WorkflowModel in parameters['__workflow__'] and
    executes it with a headless NetworkExecutor when triggered.
    Dynamic input/output ports are recreated from parameters['__port_defs__']
    via restore_from_parameters() which the engine calls before each run.
    """
    name = "group_node"
    description = "Collapsed group of nodes — double-click to inspect"
    category = "Group"

    def __init__(self):
        super().__init__(use_exec=True)
        # Fixed failure branch — fires when the inner graph reports an error;
        # exec_out fires only on success. Both are fixed ports (not in __port_defs__).
        self.add_exec_output("exec_fail")
        # Dynamic ports are added at group-creation time and restored at load time.
        # These three keys are always present so serialization has stable keys.
        self.parameters.setdefault("__workflow__", {})
        self.parameters.setdefault("__port_defs__", [])
        self.parameters.setdefault("__name__", "Group")

    # ------------------------------------------------------------------
    # Port restoration (called by engine before each execution)
    # ------------------------------------------------------------------

    def restore_from_parameters(self, parameters):
        port_defs = parameters.get("__port_defs__", [])
        for pd in port_defs:
            name = pd.get("name", "")
            data_type = pd.get("type", "any")
            if not name:
                continue
            if pd.get("is_input", True):
                if name not in self.inputs:
                    self.add_input(name, data_type)
            else:
                if name not in self.outputs:
                    self.add_output(name, data_type)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, inputs):
        from src.core.models import WorkflowModel
        from src.core.graph import GraphManager
        from src.core.engine import NetworkExecutor
        from src.nodes.base import BaseNode as _BaseNode

        workflow_json = self.parameters.get("__workflow__", {})
        if not workflow_json:
            self.log_error("Group node has no internal workflow.")
            await self.set_output("exec_fail", True)
            return {"exec_out": False, "exec_fail": True}

        try:
            workflow = WorkflowModel.model_validate(workflow_json)
        except Exception as e:
            self.log_error(f"Failed to load internal workflow: {e}")
            await self.set_output("exec_fail", True)
            return {"exec_out": False, "exec_fail": True}

        # Inject external input values into group_in nodes.
        # Use '_injected_value' (not 'value') because 'value' is an output port and
        # the engine's clear_outputs() wipes parameters["value"] back to None during
        # node prep — before execute() is ever called.
        for node_model in workflow.nodes:
            if node_model.node_id == "group_in":
                port_name = node_model.parameters.get("port_name", "")
                if port_name and port_name in inputs:
                    node_model.parameters["_injected_value"] = inputs[port_name]

        gm = GraphManager()
        gm.from_model(workflow)

        # Track inner node errors so we can choose the correct exec branch.
        inner_errors = []
        def _capture_error(nid, msg):
            inner_errors.append(msg)
            node_model = gm.nodes.get(nid)
            label = node_model.node_id if node_model else str(nid)
            self.log_error(f"[{label}] {msg}")

        def _forward_log(nid, msg, lvl):
            node_model = gm.nodes.get(nid)
            label = node_model.node_id if node_model else str(nid)
            if lvl == "error":
                self.log_error(f"[{label}] {msg}")
            elif lvl == "success":
                self.log_success(f"[{label}] {msg}")
            else:
                self.log_info(f"[{label}] {msg}")

        # Preserve outer execution memory — the sub-executor clears it on entry
        saved_memory = dict(_BaseNode.memory)
        sub_executor = NetworkExecutor(gm)
        sub_executor.node_error.connect(_capture_error)
        sub_executor.node_log.connect(_forward_log)
        def _forward_child_output(nid, results):
            if self._on_subgraph_output:
                self._on_subgraph_output([], nid, results)

        def _forward_nested_output(group_path, nid, results):
            if self._on_subgraph_output:
                self._on_subgraph_output(group_path, nid, results)

        sub_executor.node_output.connect(_forward_child_output)
        sub_executor.subgraph_node_output.connect(_forward_nested_output)
        try:
            await sub_executor.run()
        finally:
            _BaseNode.memory.clear()
            _BaseNode.memory.update(saved_memory)

        # exec_fail fires only when the inner graph has an unhandled exception.
        # Semantic failures (e.g. maya_headless success=False) are the inner graph's
        # responsibility — it routes them via its own exec pins (e.g. if_condition).
        inner_success = len(inner_errors) == 0

        # Build a map: group_out inst_id → (source_node_id, source_port)
        # Reading directly from the source avoids timing issues where group_out
        # (a pure data entry-node) executed before the exec chain populated its value.
        group_out_sources = {}
        for conn in workflow.connections:
            if conn.is_exec:
                continue
            target = gm.nodes.get(conn.to_node)
            if target and target.node_id == "group_out" and conn.to_port == "value":
                group_out_sources[conn.to_node] = (conn.from_node, conn.from_port)

        # Collect outputs from group_out nodes
        data_results = {}
        for inst_id, node_model in gm.nodes.items():
            if node_model.node_id == "group_out":
                port_name = node_model.parameters.get("port_name", "")
                if not port_name:
                    continue
                if inst_id in group_out_sources:
                    src_id, src_port = group_out_sources[inst_id]
                    value = sub_executor.node_results.get(src_id, {}).get(src_port)
                else:
                    value = sub_executor.node_results.get(inst_id, {}).get("value")
                data_results[port_name] = value

        group_name = self.parameters.get("__name__", "Group")
        self.log_info(f"Group '{group_name}' finished — success={inner_success}, outputs={len(data_results)}.")

        # Push data outputs reactively before triggering exec flow so downstream
        # nodes see correct values when the exec chain continues.
        for port_name, value in data_results.items():
            await self.set_output(port_name, value)

        # Fire exec_out on success, exec_fail on failure so the outer graph can
        # route the two outcomes to separate downstream paths.
        if inner_success:
            await self.set_output("exec_out", True)
            data_results["exec_out"] = True
            data_results["exec_fail"] = False
        else:
            self.log_error(f"Group '{group_name}' inner execution reported failure.")
            await self.set_output("exec_fail", True)
            data_results["exec_out"] = False
            data_results["exec_fail"] = True

        return data_results
