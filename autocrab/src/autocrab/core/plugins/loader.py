import importlib
import inspect
import sys
import os
from typing import Callable, Dict, Any, List, Optional, Coroutine
from autocrab.core.models.api import ToolDefinition, FunctionSpec
from autocrab.core.plugins.base import BasePlugin, ChannelPlugin, ChannelEvent
from autocrab.core.plugins.skills import load_skills_from_dir, SkillEntry as SkillMdEntry
from autocrab.core.models.config import settings
from pathlib import Path

# Registry pattern to store dynamically loaded skills
_SKILL_REGISTRY: Dict[str, Callable] = {}
_SKILL_SCHEMAS: List[ToolDefinition] = []

# Registry for other plugin types
_CHANNEL_PLUGINS: Dict[str, ChannelPlugin] = {}
_INSTALLED_PLUGINS: Dict[str, BasePlugin] = {}
_MARKDOWN_SKILLS: List[SkillMdEntry] = []

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
        
    for filename in os.listdir(directory_path):
        if filename.endswith(".py") and not filename.startswith("__"):
            file_path = os.path.join(directory_path, filename)
            # Create a unique module name for the registry
            rel_path = os.path.relpath(file_path, os.getcwd())
            module_name = rel_path.replace(os.path.sep, ".").strip(".")
            
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
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

async def start_all_channels(on_event: Optional[Callable[[ChannelEvent], Coroutine[Any, Any, None]]] = None):
    for plugin_id, plugin in _CHANNEL_PLUGINS.items():
        try:
            if on_event:
                plugin.on_event = on_event
            await plugin.start()
        except Exception as e:
            print(f"Failed to start channel {plugin_id}: {e}")

async def stop_all_channels():
    for plugin_id, plugin in _CHANNEL_PLUGINS.items():
        try:
            await plugin.stop()
        except Exception as e:
            print(f"Failed to stop channel {plugin_id}: {e}")

def discover_markdown_skills():
    """
    Discovers original AutoCrab skills from the autocrab/skills directory.
    """
    global _MARKDOWN_SKILLS
    # Resolve the skills directory relative to the autocrab project root
    # settings.config_root is usually ~/.autocrab_v2
    # But the source skills are copied to the autocrab/skills/ folder in the project.
    
    # We can use a search path:
    # 1. Project root / skills
    # 2. Config root / skills
    
    project_root = Path(os.getcwd())
    paths_to_check = [
        project_root / "skills",
        settings.config_root / "skills"
    ]
    
    all_skills = []
    seen_names = set()
    
    for path in paths_to_check:
        if path.exists():
            found = load_skills_from_dir(path)
            for s in found:
                if s.name not in seen_names:
                    all_skills.append(s)
                    seen_names.add(s.name)
                    
    _MARKDOWN_SKILLS = all_skills
    print(f"Discovered {len(_MARKDOWN_SKILLS)} markdown skills.")

def get_markdown_skills() -> List[SkillMdEntry]:
    if not _MARKDOWN_SKILLS:
        discover_markdown_skills()
    return _MARKDOWN_SKILLS
