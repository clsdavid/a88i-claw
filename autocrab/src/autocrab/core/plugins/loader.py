import importlib
import inspect
import sys
from typing import Callable, Dict, Any, List
from autocrab.core.models.api import ToolDefinition, FunctionSpec
from autocrab.core.plugins.base import BasePlugin, ChannelPlugin

# Registry pattern to store dynamically loaded skills
_SKILL_REGISTRY: Dict[str, Callable] = {}
_SKILL_SCHEMAS: List[ToolDefinition] = []

# Registry for other plugin types
_CHANNEL_PLUGINS: Dict[str, ChannelPlugin] = {}
_INSTALLED_PLUGINS: Dict[str, BasePlugin] = {}

def skill(name: str, description: str):
    """
    Decorator to register a Python function as an AutoCrab Skill.
    This entirely replaces the complex ESM module loading from the Node.js architecture.
    """
    def decorator(func: Callable):
        # 1. Register the callable execution
        _SKILL_REGISTRY[name] = func
        
        # 2. Extract Type Hints to build the Pydantic/OpenAI JSON Schema automatically
        sig = inspect.signature(func)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            param_type = "string"  # Default fallback
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == bool:
                param_type = "boolean"
                
            properties[param_name] = {"type": param_type}
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
                
        # Build the OpenAPI compatible spec
        spec = FunctionSpec(
            name=name,
            description=description,
            parameters={
                "type": "object",
                "properties": properties,
                "required": required
            }
        )
        
        _SKILL_SCHEMAS.append(ToolDefinition(type="function", function=spec))
        
        return func
    return decorator

def load_plugins_from_directory(directory_path: str):
    """
    Dynamically loads all .py files in a directory to trigger the @skill decorators.
    """
    import os
    if not os.path.exists(directory_path):
        return
        
    sys.path.insert(0, directory_path)
    
    for filename in os.listdir(directory_path):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = filename[:-3]
            try:
                module = importlib.import_module(module_name)
                # After importing, look for BasePlugin subclasses defined in the module
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj is not BasePlugin and obj is not ChannelPlugin:
                        plugin_instance = obj()
                        _INSTALLED_PLUGINS[plugin_instance.id] = plugin_instance
                        if isinstance(plugin_instance, ChannelPlugin):
                            _CHANNEL_PLUGINS[plugin_instance.id] = plugin_instance
                            print(f"Registered Channel Plugin: {plugin_instance.id}")
                        else:
                            print(f"Registered General Plugin: {plugin_instance.id}")
                
                print(f"Loaded Plugin Module: {module_name}")
            except Exception as e:
                print(f"Failed to load plugin {module_name}: {e}")
                
    sys.path.pop(0)

def get_registered_schemas() -> List[ToolDefinition]:
    return _SKILL_SCHEMAS

def execute_skill(name: str, kwargs: Dict[str, Any]) -> Any:
    if name not in _SKILL_REGISTRY:
        raise ValueError(f"Skill {name} not found in registry.")
    return _SKILL_REGISTRY[name](**kwargs)

def get_channel_plugin(channel_id: str) -> Optional[ChannelPlugin]:
    return _CHANNEL_PLUGINS.get(channel_id)

def list_channel_plugins() -> List[str]:
    return list(_CHANNEL_PLUGINS.keys())

async def start_all_channels():
    for plugin_id, plugin in _CHANNEL_PLUGINS.items():
        try:
            await plugin.start()
        except Exception as e:
            print(f"Failed to start channel {plugin_id}: {e}")

async def stop_all_channels():
    for plugin_id, plugin in _CHANNEL_PLUGINS.items():
        try:
            await plugin.stop()
        except Exception as e:
            print(f"Failed to stop channel {plugin_id}: {e}")
