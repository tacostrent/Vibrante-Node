from abc import ABC, abstractmethod
from typing import Dict, Any, List, Type, Optional

class Port:
    def __init__(self, name: str, data_type: str = "any", widget_type: str = None, options: List[str] = None, default: Any = None):
        self.name = name
        self.data_type = data_type
        self.widget_type = widget_type
        self.options = options
        self.default = default

class BaseNode(ABC):
    name: str = "BaseNode"
    description: str = ""
    category: str = "General"
    icon_path: Optional[str] = None
    
    # Shared memory for variables during a single execution run
    memory: Dict[str, Any] = {}

    def __init__(self, use_exec: bool = True):
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}
        self.parameters: Dict[str, Any] = {}
        self.parameter_types: Dict[str, Type] = {}
        self._on_log = None # Hook for engine to capture logs
        self._pending_logs: List[tuple] = [] # Buffer for log calls made before _on_log is set
        self._on_output = None # Hook for engine to capture intermediate outputs
        self._on_subgraph_output = None
        self._check_stopped = None # Hook for engine to check cancellation
        self._on_ports_changed = None # Hook for UI to rebuild ports
        self._is_port_connected = None # Hook for UI to check connections
        self._on_dropdown_options_changed = None # Hook for UI to update dropdown items
        
        if use_exec:
            # DEFAULT pins if requested
            self.add_exec_input("exec_in")
            self.add_exec_output("exec_out")

    def rebuild_ports(self):
        """Notifies the UI to rebuild the node's ports."""
        if self._on_ports_changed:
            self._on_ports_changed()

    def is_port_connected(self, name: str, is_input: bool) -> bool:
        """Checks if a port is connected via the UI hook."""
        if self._is_port_connected:
            return self._is_port_connected(name, is_input)
        return False

    def is_stopped(self) -> bool:
        """Checks if the execution has been requested to stop."""
        if self._check_stopped:
            return self._check_stopped()
        return False

    async def set_output(self, name: str, value: Any):
        """Allows a node to push output data during execution (streaming)."""
        if name in self.outputs:
            self.parameters[name] = value
            if self._on_output:
                await self._on_output(name, value)

    def clear_outputs(self):
        """Resets all output parameters to their defaults before a new execution."""
        for name, port in self.outputs.items():
            self.parameters[name] = port.default

    def log_info(self, msg: str):
        if self._on_log: self._on_log(msg, "info")
        else: self._pending_logs.append((msg, "info"))

    def log_success(self, msg: str):
        if self._on_log: self._on_log(msg, "success")
        else: self._pending_logs.append((msg, "success"))

    def log_error(self, msg: str):
        if self._on_log: self._on_log(msg, "error")
        else: self._pending_logs.append((msg, "error"))

    def _flush_pending_logs(self):
        if self._on_log and self._pending_logs:
            for msg, lvl in self._pending_logs:
                self._on_log(msg, lvl)
            self._pending_logs.clear()

    def add_input(self, name: str, data_type: str = "any", widget_type: str = None, options: List[str] = None, default: Any = None):
        # Provide sensible defaults instead of None for certain types
        if default is None:
            if data_type == "string": default = ""
            elif data_type == "list": default = []
            elif data_type == "bool": default = False
            elif data_type in ["int", "float", "number"]: default = 0
            
        self.inputs[name] = Port(name, data_type, widget_type, options, default)
        # Always initialize parameter key to ensure it's accessible via .parameters.get()
        if name not in self.parameters:
            self.parameters[name] = default

    def add_exec_input(self, name: str = "exec_in"):
        self.add_input(name, data_type="exec")

    def add_output(self, name: str, data_type: str = "any", default: Any = None):
        # Provide sensible defaults instead of None for certain types
        if default is None:
            if data_type == "string": default = ""
            elif data_type == "list": default = []
            elif data_type == "bool": default = False
            elif data_type in ["int", "float", "number"]: default = 0

        self.outputs[name] = Port(name, data_type, default=default)
        # ALSO initialize output name in parameters so other nodes can query its 'last known' or 'default' state
        if name not in self.parameters:
            self.parameters[name] = default

    def add_exec_output(self, name: str = "exec_out"):
        self.add_output(name, data_type="exec")

    def add_parameter(self, name: str, param_type: Type, default: Any = None):
        self.parameter_types[name] = param_type
        self.parameters[name] = default

    def restore_from_parameters(self, parameters: Dict[str, Any]):
        """Optional hook to restore dynamic state (like ports) from saved parameters."""
        pass

    def set_parameter(self, name: str, value: Any):
        """Set a parameter value. If the port is a dropdown and value is a list, updates options
        and preserves the current selection when it still exists in the new list, otherwise
        falls back to the first item."""
        if isinstance(value, list) and name in self.inputs and self.inputs[name].widget_type == "dropdown":
            self.inputs[name].options = value
            current = self.parameters.get(name)
            self.parameters[name] = current if (current and current in value) else (value[0] if value else "")
            if self._on_dropdown_options_changed:
                self._on_dropdown_options_changed(name, value)
        else:
            self.parameters[name] = value

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Safely retrieve a parameter value."""
        return self.parameters.get(name, default)

    def __getitem__(self, key: str) -> Any:
        """Shortcut for get_parameter: node['param_name']"""
        return self.get_parameter(key)

    async def on_plug(self, port_name: str, is_input: bool, other_node: 'BaseNode', other_port_name: str):
        """Called when a connection is established (Async)."""
        pass

    async def on_unplug(self, port_name: str, is_input: bool):
        """Called when a connection is removed (Async)."""
        pass

    def on_plug_sync(self, port_name: str, is_input: bool, other_node: 'BaseNode', other_port_name: str):
        """Called when a connection is established (Sync)."""
        pass

    def on_unplug_sync(self, port_name: str, is_input: bool):
        """Called when a connection is removed (Sync)."""
        pass

    async def on_parameter_changed(self, name: str, value: Any):
        """Called when a parameter/widget value is changed."""
        pass

    @abstractmethod
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution logic for the node.
        :param inputs: Dictionary of input data from connected nodes.
        :return: Dictionary of output data.
        """
        pass

class NodeRegistry:
    _nodes: Dict[str, Type[BaseNode]] = {}

    @classmethod
    def register(cls, node_class: Type[BaseNode]):
        cls._nodes[node_class.name] = node_class

    @classmethod
    def get_node_class(cls, name: str) -> Optional[Type[BaseNode]]:
        return cls._nodes.get(name)

    @classmethod
    def list_nodes(cls) -> List[str]:
        return list(cls._nodes.keys())
