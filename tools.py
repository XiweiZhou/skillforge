#!/usr/bin/env python3
"""
SkillForge MCP Tool Layer

Bridges declarative tool declarations in SKILL.md to actual tool handlers
from the services/ directory. Provides the ToolExecutor that the LLM
provider interacts with during skill execution.
"""

import importlib
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable

from llm import ToolCall, ToolResult

logger = logging.getLogger("Tools")


@dataclass
class ToolDefinition:
    """
    Definition of a tool available to the LLM during execution.

    Parsed from SKILL.md metadata.tools declarations.
    Sent to the LLM so it knows what tools it can call.
    """
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_params: List[str] = field(default_factory=list)

    def to_llm_schema(self) -> Dict[str, Any]:
        """Convert to provider-agnostic JSON schema for LLM tool definitions."""
        return {
            'name': self.name,
            'description': self.description,
            'parameters': {
                'type': 'object',
                'properties': self.parameters,
                'required': self.required_params,
            },
        }


class ToolExecutor:
    """
    Executes tool calls by routing to registered handlers.

    When the LLM requests a tool call, the executor looks up the handler
    and invokes it. Adapts ServiceResponse from existing services/ to ToolResult.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable[..., Any]] = {}

    def register(self, tool_name: str, handler: Callable[..., Any]):
        """Register a handler function for a tool name."""
        self._handlers[tool_name] = handler

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        handler = self._handlers.get(tool_call.tool_name)
        if not handler:
            return ToolResult(
                call_id=tool_call.call_id,
                success=False,
                error=f"Unknown tool: {tool_call.tool_name}",
            )
        try:
            result = handler(**tool_call.arguments)

            # Adapt ServiceResponse to ToolResult
            from services.service_base import ServiceResponse
            if isinstance(result, ServiceResponse):
                return ToolResult(
                    call_id=tool_call.call_id,
                    success=result.success,
                    data=result.data,
                    error=result.error,
                )

            # If handler returns a ToolResult directly
            if isinstance(result, ToolResult):
                result.call_id = tool_call.call_id
                return result

            # Raw return value
            return ToolResult(
                call_id=tool_call.call_id,
                success=True,
                data=result,
            )
        except Exception as e:
            logger.error(f"Tool execution error for {tool_call.tool_name}: {e}")
            return ToolResult(
                call_id=tool_call.call_id,
                success=False,
                error=str(e),
            )

    def execute_all(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """Execute multiple tool calls and return all results."""
        return [self.execute(tc) for tc in tool_calls]


class ToolRegistry:
    """
    Discovers and manages tool definitions from SKILL.md metadata.

    Bridges declarative tool declarations to actual service handlers
    from the services/ directory.
    """

    BUILTIN_TOOLS: Dict[str, Dict[str, Any]] = {
        'web_search': {
            'description': 'Search the web for information',
            'parameters': {
                'query': {'type': 'string', 'description': 'Search query'},
            },
            'required': ['query'],
            'service_module': 'services.web_search_api',
            'service_class': 'MockWebSearchAPI',
            'method': 'search',
        },
        'calendar_availability': {
            'description': 'Check calendar availability for participants',
            'parameters': {
                'date': {'type': 'string', 'description': 'Date in YYYY-MM-DD format'},
                'participant_emails': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Email addresses of participants',
                },
            },
            'required': ['date', 'participant_emails'],
            'service_module': 'services.mock_calendar_mcp',
            'service_class': 'MockCalendarMCP',
            'method': 'get_availability',
        },
        'calendar_schedule': {
            'description': 'Schedule a meeting',
            'parameters': {
                'title': {'type': 'string', 'description': 'Meeting title'},
                'start_time': {'type': 'string', 'description': 'Start time'},
                'end_time': {'type': 'string', 'description': 'End time'},
                'participants': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Participant email addresses',
                },
            },
            'required': ['title', 'start_time', 'end_time', 'participants'],
            'service_module': 'services.mock_calendar_mcp',
            'service_class': 'MockCalendarMCP',
            'method': 'schedule_meeting',
        },
        'source_credibility': {
            'description': 'Check the credibility of a web source',
            'parameters': {
                'url': {'type': 'string', 'description': 'URL to check'},
            },
            'required': ['url'],
            'service_module': 'services.web_search_api',
            'service_class': 'MockWebSearchAPI',
            'method': 'get_source_credibility',
        },
    }

    def __init__(self):
        self._definitions: Dict[str, ToolDefinition] = {}
        self._executor = ToolExecutor()
        self._service_instances: Dict[str, Any] = {}

    def load_tools_for_skill(self, tool_names: List[str]):
        """
        Load tool definitions and wire up handlers for the given tool names.

        Called when a DeclarativeSkill is constructed, based on its
        metadata.tools list from SKILL.md.
        """
        for name in tool_names:
            if name in self._definitions:
                continue  # Already loaded
            if name in self.BUILTIN_TOOLS:
                spec = self.BUILTIN_TOOLS[name]
                defn = ToolDefinition(
                    name=name,
                    description=spec['description'],
                    parameters=spec['parameters'],
                    required_params=spec['required'],
                )
                self._definitions[name] = defn
                self._wire_builtin_handler(name, spec)
                logger.info(f"Loaded tool: {name}")
            else:
                logger.warning(f"Unknown tool: {name} (not in BUILTIN_TOOLS)")

    def _wire_builtin_handler(self, tool_name: str, spec: Dict):
        """Lazily instantiate service and register its method as a handler."""
        module = importlib.import_module(spec['service_module'])
        cls = getattr(module, spec['service_class'])

        cache_key = f"{spec['service_module']}.{spec['service_class']}"
        if cache_key not in self._service_instances:
            instance = cls()
            instance.connect()
            self._service_instances[cache_key] = instance

        instance = self._service_instances[cache_key]
        method = getattr(instance, spec['method'])
        self._executor.register(tool_name, method)

    def get_definitions(self) -> List[ToolDefinition]:
        """Get all loaded tool definitions."""
        return list(self._definitions.values())

    def get_executor(self) -> ToolExecutor:
        """Get the tool executor with registered handlers."""
        return self._executor

    def register_custom_tool(self, definition: ToolDefinition,
                             handler: Callable):
        """Register a custom tool (for testing or extension)."""
        self._definitions[definition.name] = definition
        self._executor.register(definition.name, handler)
