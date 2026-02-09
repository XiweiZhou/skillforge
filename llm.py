#!/usr/bin/env python3
"""
SkillForge LLM Provider Layer

Provider-agnostic abstraction for LLM-powered skill execution.
Supports Claude, OpenAI, DeepSeek, and custom providers.
Falls back to template-based execution when no provider is configured.
"""

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

logger = logging.getLogger("LLM")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    """A tool call requested by the LLM."""
    tool_name: str
    arguments: Dict[str, Any]
    call_id: str = ""

    def __post_init__(self):
        if not self.call_id:
            self.call_id = f"tc_{uuid.uuid4().hex[:8]}"


@dataclass
class ToolResult:
    """Result of executing a tool call."""
    call_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None


@dataclass
class LLMRequest:
    """Structured request to the LLM."""
    task_description: str
    skill_name: str
    skill_description: str
    templates: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    available_tools: List[Dict[str, Any]] = field(default_factory=list)
    system_prompt: Optional[str] = None


@dataclass
class LLMResponse:
    """Structured response from the LLM."""
    intent: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[ToolCall] = field(default_factory=list)
    reasoning: Optional[str] = None
    raw_response: Optional[str] = None


# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Implementations: ClaudeProvider, OpenAIProvider, DeepSeekProvider, MockProvider.
    """

    @abstractmethod
    def classify_intent(self, request: LLMRequest) -> str:
        """Classify the user's intent from the task description."""
        pass

    @abstractmethod
    def generate(self, request: LLMRequest,
                 tool_results: Optional[List[ToolResult]] = None) -> LLMResponse:
        """
        Generate content for the task, optionally using tool results.

        Flow:
        1. Framework calls generate() with the request
        2. If LLMResponse.tool_calls is non-empty, framework executes tools
        3. Framework calls generate() again with tool_results populated
        4. LLM produces final content using tool data
        """
        pass

    @abstractmethod
    def classify_error(self, error_message: str,
                       known_types: List[str]) -> str:
        """Classify an error message into a known error type."""
        pass

    def is_available(self) -> bool:
        """Check if this provider is ready (API key set, etc.)."""
        return True


# ---------------------------------------------------------------------------
# MockProvider -- deterministic, reuses template logic for tests
# ---------------------------------------------------------------------------

class MockProvider(LLMProvider):
    """
    Deterministic provider that replicates template-based behavior.

    Used for testing and as a reference implementation. Accepts optional
    preconfigured responses for test-specific overrides.
    """

    def __init__(self, responses: Optional[Dict[str, Any]] = None):
        self._responses = responses or {}

    def classify_intent(self, request: LLMRequest) -> str:
        if 'classify_intent' in self._responses:
            return self._responses['classify_intent']

        task = request.task_description.lower()
        for intent_name, template in request.templates.items():
            match_keywords = template.get('match', [])
            if any(kw in task for kw in match_keywords):
                return intent_name

        if request.templates:
            return list(request.templates.keys())[-1]
        return 'general'

    def generate(self, request: LLMRequest,
                 tool_results: Optional[List[ToolResult]] = None) -> LLMResponse:
        if 'generate' in self._responses:
            resp = self._responses['generate']
            if isinstance(resp, LLMResponse):
                return resp
            return LLMResponse(**resp)

        intent = self.classify_intent(request)

        if intent in request.templates:
            template = request.templates[intent]
            content = {k: v for k, v in template.items() if k != 'match'}
        else:
            content = {'content': f'Output for: {request.task_description}'}

        # Include tool results in content if available
        if tool_results:
            tool_data = {}
            for tr in tool_results:
                if tr.success and tr.data is not None:
                    tool_data[tr.call_id] = tr.data
            if tool_data:
                content['tool_data'] = tool_data

        return LLMResponse(intent=intent, content=content)

    def classify_error(self, error_message: str,
                       known_types: List[str]) -> str:
        if 'classify_error' in self._responses:
            return self._responses['classify_error']

        error_lower = error_message.lower()
        for error_type in known_types:
            base = error_type.replace('Error', '').lower()
            if base in error_lower:
                return error_type
        if 'spam' in error_lower:
            return 'SpamTriggerError'
        if 'vague' in error_lower:
            return 'PoorQueryError'
        return 'GenericError'


# ---------------------------------------------------------------------------
# OpenAI-compatible provider (base for OpenAI and DeepSeek)
# ---------------------------------------------------------------------------

class _OpenAICompatibleProvider(LLMProvider):
    """
    Base provider for OpenAI-compatible APIs (OpenAI, DeepSeek, etc.).

    Subclasses set default model, base_url, and API key env var.
    """

    def __init__(self, model: Optional[str] = None,
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None):
        self._model = model or self._default_model()
        self._api_key = api_key or os.environ.get(self._api_key_env(), '')
        self._base_url = base_url or self._default_base_url()
        self._client = None

    def _default_model(self) -> str:
        return "gpt-4o"

    def _default_base_url(self) -> str:
        return "https://api.openai.com/v1"

    def _api_key_env(self) -> str:
        return "OPENAI_API_KEY"

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: pip install openai"
                )
        return self._client

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _build_system_prompt(self, request: LLMRequest) -> str:
        return (
            f"You are the '{request.skill_name}' skill. "
            f"Description: {request.skill_description}\n\n"
            f"Available templates: {json.dumps(list(request.templates.keys()))}\n"
            f"Context: {json.dumps(request.context)}\n\n"
            "Respond with a JSON object containing:\n"
            '- "intent": one of the template names or a new intent\n'
            '- "content": dict with the generated output fields '
            '(e.g. "subject", "body" for emails)\n'
            '- "reasoning": brief explanation of your choices\n'
        )

    def classify_intent(self, request: LLMRequest) -> str:
        client = self._get_client()
        template_names = list(request.templates.keys()) if request.templates else []

        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": (
                    f"Classify the user's intent into one of: {template_names}. "
                    "Respond with just the intent name."
                )},
                {"role": "user", "content": request.task_description},
            ],
            max_tokens=50,
        )
        intent = response.choices[0].message.content.strip().lower()
        # Map to closest template if exact match not found
        if intent in request.templates:
            return intent
        for name in template_names:
            if name in intent or intent in name:
                return name
        return template_names[-1] if template_names else 'general'

    def generate(self, request: LLMRequest,
                 tool_results: Optional[List[ToolResult]] = None) -> LLMResponse:
        client = self._get_client()
        system_prompt = request.system_prompt or self._build_system_prompt(request)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.task_description},
        ]

        if tool_results:
            tool_data_str = json.dumps([
                {"call_id": tr.call_id, "success": tr.success,
                 "data": tr.data, "error": tr.error}
                for tr in tool_results
            ])
            messages.append({
                "role": "user",
                "content": f"Tool results:\n{tool_data_str}\n\n"
                           "Use these results to generate the final output.",
            })

        # Build tool definitions for function calling if available
        tools = None
        if request.available_tools and not tool_results:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t['name'],
                        "description": t.get('description', ''),
                        "parameters": t.get('parameters', {}),
                    },
                }
                for t in request.available_tools
            ]

        kwargs = {"model": self._model, "messages": messages, "max_tokens": 1024}
        if tools:
            kwargs["tools"] = tools

        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        # Check for tool calls
        if message.tool_calls:
            calls = [
                ToolCall(
                    tool_name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                    call_id=tc.id,
                )
                for tc in message.tool_calls
            ]
            return LLMResponse(tool_calls=calls, raw_response=message.content)

        # Parse structured response
        raw = message.content or ''
        try:
            # Try to extract JSON from response
            json_start = raw.find('{')
            json_end = raw.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(raw[json_start:json_end])
                return LLMResponse(
                    intent=parsed.get('intent', 'general'),
                    content=parsed.get('content', {'body': raw}),
                    reasoning=parsed.get('reasoning'),
                    raw_response=raw,
                )
        except (json.JSONDecodeError, KeyError):
            pass

        return LLMResponse(
            intent='general',
            content={'body': raw},
            raw_response=raw,
        )

    def classify_error(self, error_message: str,
                       known_types: List[str]) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": (
                    f"Classify this error into one of: {known_types}. "
                    "If none match, respond with GenericError. "
                    "Respond with just the error type name."
                )},
                {"role": "user", "content": error_message},
            ],
            max_tokens=50,
        )
        result = response.choices[0].message.content.strip()
        return result if result in known_types else 'GenericError'


class OpenAIProvider(_OpenAICompatibleProvider):
    """OpenAI provider using the openai SDK."""
    pass


class DeepSeekProvider(_OpenAICompatibleProvider):
    """DeepSeek provider using the OpenAI-compatible API."""

    def _default_model(self) -> str:
        return "deepseek-chat"

    def _default_base_url(self) -> str:
        return "https://api.deepseek.com"

    def _api_key_env(self) -> str:
        return "DEEPSEEK_API_KEY"


# ---------------------------------------------------------------------------
# Claude provider
# ---------------------------------------------------------------------------

class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider using the anthropic SDK."""

    def __init__(self, model: Optional[str] = None,
                 api_key: Optional[str] = None):
        self._model = model or "claude-sonnet-4-20250514"
        self._api_key = api_key or os.environ.get('ANTHROPIC_API_KEY', '')
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self._api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )
        return self._client

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _build_system_prompt(self, request: LLMRequest) -> str:
        return (
            f"You are the '{request.skill_name}' skill. "
            f"Description: {request.skill_description}\n\n"
            f"Available templates: {json.dumps(list(request.templates.keys()))}\n"
            f"Context: {json.dumps(request.context)}\n\n"
            "Respond with a JSON object containing:\n"
            '- "intent": one of the template names or a new intent\n'
            '- "content": dict with the generated output fields '
            '(e.g. "subject", "body" for emails)\n'
            '- "reasoning": brief explanation of your choices\n'
        )

    def classify_intent(self, request: LLMRequest) -> str:
        client = self._get_client()
        template_names = list(request.templates.keys()) if request.templates else []

        response = client.messages.create(
            model=self._model,
            max_tokens=50,
            system=(
                f"Classify the user's intent into one of: {template_names}. "
                "Respond with just the intent name."
            ),
            messages=[{"role": "user", "content": request.task_description}],
        )
        intent = response.content[0].text.strip().lower()
        if intent in request.templates:
            return intent
        for name in template_names:
            if name in intent or intent in name:
                return name
        return template_names[-1] if template_names else 'general'

    def generate(self, request: LLMRequest,
                 tool_results: Optional[List[ToolResult]] = None) -> LLMResponse:
        client = self._get_client()
        system_prompt = request.system_prompt or self._build_system_prompt(request)

        messages = [{"role": "user", "content": request.task_description}]

        if tool_results:
            tool_data_str = json.dumps([
                {"call_id": tr.call_id, "success": tr.success,
                 "data": tr.data, "error": tr.error}
                for tr in tool_results
            ])
            messages.append({
                "role": "assistant",
                "content": "I'll process the tool results.",
            })
            messages.append({
                "role": "user",
                "content": f"Tool results:\n{tool_data_str}\n\n"
                           "Use these results to generate the final output.",
            })

        # Build tool definitions for Claude tool use
        tools = None
        if request.available_tools and not tool_results:
            tools = [
                {
                    "name": t['name'],
                    "description": t.get('description', ''),
                    "input_schema": t.get('parameters', {}),
                }
                for t in request.available_tools
            ]

        kwargs = {
            "model": self._model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = client.messages.create(**kwargs)

        # Check for tool use
        tool_calls = []
        text_content = ''
        for block in response.content:
            if block.type == 'tool_use':
                tool_calls.append(ToolCall(
                    tool_name=block.name,
                    arguments=block.input,
                    call_id=block.id,
                ))
            elif block.type == 'text':
                text_content += block.text

        if tool_calls:
            return LLMResponse(tool_calls=tool_calls, raw_response=text_content)

        # Parse structured response
        raw = text_content
        try:
            json_start = raw.find('{')
            json_end = raw.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(raw[json_start:json_end])
                return LLMResponse(
                    intent=parsed.get('intent', 'general'),
                    content=parsed.get('content', {'body': raw}),
                    reasoning=parsed.get('reasoning'),
                    raw_response=raw,
                )
        except (json.JSONDecodeError, KeyError):
            pass

        return LLMResponse(
            intent='general',
            content={'body': raw},
            raw_response=raw,
        )

    def classify_error(self, error_message: str,
                       known_types: List[str]) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=50,
            system=(
                f"Classify this error into one of: {known_types}. "
                "If none match, respond with GenericError. "
                "Respond with just the error type name."
            ),
            messages=[{"role": "user", "content": error_message}],
        )
        result = response.content[0].text.strip()
        return result if result in known_types else 'GenericError'
