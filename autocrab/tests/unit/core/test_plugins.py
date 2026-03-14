import pytest
from autocrab.core.plugins.loader import skill, get_registered_schemas, execute_skill, _SKILL_REGISTRY, _SKILL_SCHEMAS

def test_skill_registration():
    # clear registry for test
    _SKILL_REGISTRY.clear()
    _SKILL_SCHEMAS.clear()

    @skill("test_action", "A test skill")
    def my_skill(x: int, y: int = 5) -> int:
        return x + y

    schemas = get_registered_schemas()
    assert len(schemas) == 1
    spec = schemas[0].function
    assert spec.name == "test_action"
    assert spec.description == "A test skill"
    assert "x" in spec.parameters["properties"]
    assert "y" in spec.parameters["properties"]
    assert "x" in spec.parameters["required"]
    assert "y" not in spec.parameters["required"]

    result = execute_skill("test_action", {"x": 10})
    assert result == 15

def test_execute_invalid_skill():
    with pytest.raises(ValueError, match="not found in registry"):
        execute_skill("non_existent_skill", {})
