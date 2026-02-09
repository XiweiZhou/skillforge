"""Tests for MCP tool layer: ToolDefinition, ToolExecutor, ToolRegistry."""

import pytest

from llm import ToolCall, ToolResult
from tools import ToolDefinition, ToolExecutor, ToolRegistry
from services.service_base import ServiceResponse


class TestToolDefinition:
    def test_to_llm_schema(self):
        defn = ToolDefinition(
            name="search",
            description="Search the web",
            parameters={"query": {"type": "string"}},
            required_params=["query"],
        )
        schema = defn.to_llm_schema()
        assert schema["name"] == "search"
        assert schema["description"] == "Search the web"
        assert schema["parameters"]["type"] == "object"
        assert schema["parameters"]["required"] == ["query"]
        assert "query" in schema["parameters"]["properties"]


class TestToolExecutor:
    def test_execute_registered_tool(self):
        executor = ToolExecutor()
        executor.register("greet", lambda name: f"Hello, {name}!")

        tc = ToolCall(tool_name="greet", arguments={"name": "World"})
        result = executor.execute(tc)
        assert result.success
        assert result.data == "Hello, World!"

    def test_execute_unknown_tool(self):
        executor = ToolExecutor()
        tc = ToolCall(tool_name="nonexistent", arguments={})
        result = executor.execute(tc)
        assert not result.success
        assert "Unknown tool" in result.error

    def test_execute_adapts_service_response(self):
        executor = ToolExecutor()

        def mock_service(**kwargs):
            return ServiceResponse(
                success=True,
                data={"results": ["a", "b"]},
            )

        executor.register("search", mock_service)
        tc = ToolCall(tool_name="search", arguments={"query": "test"})
        result = executor.execute(tc)
        assert result.success
        assert result.data == {"results": ["a", "b"]}
        assert result.call_id == tc.call_id

    def test_execute_handles_exception(self):
        executor = ToolExecutor()
        executor.register("bad", lambda: 1 / 0)

        tc = ToolCall(tool_name="bad", arguments={})
        result = executor.execute(tc)
        assert not result.success
        assert "division by zero" in result.error

    def test_execute_all(self):
        executor = ToolExecutor()
        executor.register("add", lambda a, b: a + b)

        calls = [
            ToolCall(tool_name="add", arguments={"a": 1, "b": 2}),
            ToolCall(tool_name="add", arguments={"a": 3, "b": 4}),
        ]
        results = executor.execute_all(calls)
        assert len(results) == 2
        assert results[0].data == 3
        assert results[1].data == 7


class TestToolRegistry:
    def test_builtin_tools_defined(self):
        assert "web_search" in ToolRegistry.BUILTIN_TOOLS
        assert "calendar_availability" in ToolRegistry.BUILTIN_TOOLS
        assert "calendar_schedule" in ToolRegistry.BUILTIN_TOOLS
        assert "source_credibility" in ToolRegistry.BUILTIN_TOOLS

    def test_load_builtin_tools(self):
        registry = ToolRegistry()
        registry.load_tools_for_skill(["web_search"])
        definitions = registry.get_definitions()
        assert len(definitions) == 1
        assert definitions[0].name == "web_search"

    def test_load_unknown_tool_ignored(self):
        registry = ToolRegistry()
        registry.load_tools_for_skill(["nonexistent_tool"])
        assert len(registry.get_definitions()) == 0

    def test_register_custom_tool(self):
        registry = ToolRegistry()
        defn = ToolDefinition(
            name="custom",
            description="Custom tool",
            parameters={"x": {"type": "integer"}},
            required_params=["x"],
        )
        registry.register_custom_tool(defn, lambda x: x * 2)

        definitions = registry.get_definitions()
        assert len(definitions) == 1

        executor = registry.get_executor()
        tc = ToolCall(tool_name="custom", arguments={"x": 5})
        result = executor.execute(tc)
        assert result.success
        assert result.data == 10

    def test_load_does_not_duplicate(self):
        registry = ToolRegistry()
        registry.load_tools_for_skill(["web_search"])
        registry.load_tools_for_skill(["web_search"])
        assert len(registry.get_definitions()) == 1

    def test_builtin_tool_execution(self):
        """Verify a builtin tool actually wires to the mock service."""
        registry = ToolRegistry()
        registry.load_tools_for_skill(["web_search"])
        executor = registry.get_executor()

        tc = ToolCall(tool_name="web_search", arguments={"query": "python programming"})
        result = executor.execute(tc)
        assert result.success
        assert result.data is not None

    def test_tool_definition_schema(self):
        registry = ToolRegistry()
        registry.load_tools_for_skill(["calendar_availability"])
        defns = registry.get_definitions()
        schema = defns[0].to_llm_schema()
        assert schema["name"] == "calendar_availability"
        assert "date" in schema["parameters"]["properties"]
