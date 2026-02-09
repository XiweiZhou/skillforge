"""Tests for LLM provider abstraction and LLM-powered execution."""

import pytest

from llm import (
    LLMProvider, LLMRequest, LLMResponse, MockProvider,
    ToolCall, ToolResult,
)
from skills import (
    DeclarativeSkill, ExecutionContext, ExecutionResult, ExecutionStatus,
    SkillOutput, SkillLoader,
)
from knowledge import KnowledgeBase, Rule, RuleType, Condition, ConditionOperator, Action


class TestLLMDataStructures:
    def test_tool_call_auto_id(self):
        tc = ToolCall(tool_name="search", arguments={"q": "test"})
        assert tc.call_id.startswith("tc_")

    def test_tool_call_explicit_id(self):
        tc = ToolCall(tool_name="search", arguments={}, call_id="my_id")
        assert tc.call_id == "my_id"

    def test_llm_request_construction(self):
        req = LLMRequest(
            task_description="Write an email",
            skill_name="email_writer",
            skill_description="Writes emails",
            templates={"greeting": {"match": ["hello"], "body": "Hi"}},
            available_tools=[{"name": "search", "description": "Search"}],
        )
        assert req.task_description == "Write an email"
        assert len(req.available_tools) == 1

    def test_llm_response_defaults(self):
        resp = LLMResponse()
        assert resp.intent == ""
        assert resp.content == {}
        assert resp.tool_calls == []


class TestMockProvider:
    def test_is_available(self):
        provider = MockProvider()
        assert provider.is_available() is True

    def test_classify_intent_keyword_matching(self):
        provider = MockProvider()
        request = LLMRequest(
            task_description="hello world",
            skill_name="test",
            skill_description="test",
            templates={
                "greeting": {"match": ["hello", "hi"], "body": "Hi"},
                "farewell": {"match": ["bye"], "body": "Bye"},
            },
        )
        assert provider.classify_intent(request) == "greeting"

    def test_classify_intent_fallback_to_last(self):
        provider = MockProvider()
        request = LLMRequest(
            task_description="completely unrelated",
            skill_name="test",
            skill_description="test",
            templates={
                "greeting": {"match": ["hello"], "body": "Hi"},
                "default": {"match": [], "body": "Default"},
            },
        )
        assert provider.classify_intent(request) == "default"

    def test_classify_intent_no_templates(self):
        provider = MockProvider()
        request = LLMRequest(
            task_description="anything",
            skill_name="test",
            skill_description="test",
        )
        assert provider.classify_intent(request) == "general"

    def test_generate_returns_template_content(self):
        provider = MockProvider()
        request = LLMRequest(
            task_description="hello world",
            skill_name="test",
            skill_description="test",
            templates={
                "greeting": {"match": ["hello"], "subject": "Hi", "body": "Hello!"},
            },
        )
        response = provider.generate(request)
        assert response.intent == "greeting"
        assert response.content["subject"] == "Hi"
        assert response.content["body"] == "Hello!"

    def test_generate_with_tool_results(self):
        provider = MockProvider()
        request = LLMRequest(
            task_description="hello",
            skill_name="test",
            skill_description="test",
            templates={"greeting": {"match": ["hello"], "body": "Hi"}},
        )
        tool_results = [
            ToolResult(call_id="tc_1", success=True, data={"key": "value"}),
        ]
        response = provider.generate(request, tool_results=tool_results)
        assert "tool_data" in response.content
        assert response.content["tool_data"]["tc_1"] == {"key": "value"}

    def test_generate_with_preconfigured_response(self):
        custom_response = LLMResponse(
            intent="custom_intent",
            content={"custom": True},
        )
        provider = MockProvider(responses={"generate": custom_response})
        request = LLMRequest(
            task_description="anything",
            skill_name="test",
            skill_description="test",
        )
        response = provider.generate(request)
        assert response.intent == "custom_intent"
        assert response.content == {"custom": True}

    def test_classify_error_keyword_matching(self):
        provider = MockProvider()
        assert provider.classify_error(
            "Timezone not set", ["TimezoneError", "SpamTriggerError"]
        ) == "TimezoneError"

    def test_classify_error_spam(self):
        provider = MockProvider()
        assert provider.classify_error(
            "Spam detected", ["TimezoneError", "SpamTriggerError"]
        ) == "SpamTriggerError"

    def test_classify_error_unknown(self):
        provider = MockProvider()
        assert provider.classify_error(
            "something weird", ["TimezoneError"]
        ) == "GenericError"

    def test_classify_error_preconfigured(self):
        provider = MockProvider(responses={"classify_error": "CustomError"})
        assert provider.classify_error("anything", []) == "CustomError"


class TestLLMPoweredExecution:
    def test_llm_execution_produces_output(self, sample_skill_with_templates,
                                           knowledge_base):
        provider = MockProvider()
        skill = SkillLoader._load_skill(
            sample_skill_with_templates, knowledge_base,
            llm_provider=provider,
        )
        ctx = ExecutionContext(task_description="hello world", task_id="t1")
        result = skill.execute(ctx)

        assert result.success
        assert result.output.content["subject"] == "Greeting"
        assert result.output.metadata.get("llm_powered") is True

    def test_llm_execution_respects_validation(self, sample_skill_dir,
                                               knowledge_base):
        provider = MockProvider()
        skill = SkillLoader._load_skill(
            sample_skill_dir, knowledge_base,
            llm_provider=provider,
        )
        ctx = ExecutionContext(
            task_description="test", task_id="t1", has_attachment=False,
        )
        ctx.flags.add("attachment_mentioned")
        result = skill.execute(ctx)
        assert not result.success

    def test_llm_execution_applies_prevention_rules(self, sample_skill_dir,
                                                    knowledge_base):
        provider = MockProvider()
        skill = SkillLoader._load_skill(
            sample_skill_dir, knowledge_base,
            llm_provider=provider,
        )
        rule = Rule(
            id="test_rule", name="Test Flag",
            rule_type=RuleType.PREVENTION,
            conditions=[Condition("context.test_flag", ConditionOperator.EQUALS, True)],
            actions=[Action("flag", "_flags", "test_flagged")],
            confidence=1.0,
        )
        knowledge_base.add_rule(skill.name, rule)

        ctx = ExecutionContext(task_description="test", task_id="t1", test_flag=True)
        result = skill.execute(ctx)
        assert "test_rule" in result.rules_applied

    def test_fallback_when_no_provider(self, sample_skill_with_templates,
                                       knowledge_base):
        skill = SkillLoader._load_skill(
            sample_skill_with_templates, knowledge_base,
        )
        ctx = ExecutionContext(task_description="hello world", task_id="t1")
        result = skill.execute(ctx)

        assert result.success
        assert result.output.metadata.get("llm_powered") is None

    def test_fallback_when_provider_unavailable(self, sample_skill_with_templates,
                                                knowledge_base):
        provider = MockProvider()
        provider.is_available = lambda: False
        skill = SkillLoader._load_skill(
            sample_skill_with_templates, knowledge_base,
            llm_provider=provider,
        )
        ctx = ExecutionContext(task_description="hello world", task_id="t1")
        result = skill.execute(ctx)

        assert result.success
        assert result.output.metadata.get("llm_powered") is None

    def test_handler_takes_priority_over_llm(self, tmp_skills_dir, knowledge_base):
        skill_dir = tmp_skills_dir / "handler-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: handler-skill\ndescription: Has handler.\n---\n# H\n"
        )
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "handler.py").write_text(
            "from skills import ExecutionResult, ExecutionStatus, SkillOutput\n"
            "\n"
            "def execute(context, metadata):\n"
            "    return ExecutionResult(\n"
            "        status=ExecutionStatus.SUCCESS,\n"
            "        output=SkillOutput(content={'handler': True}, output_type='h'),\n"
            "    )\n"
        )

        provider = MockProvider()
        skill = SkillLoader._load_skill(skill_dir, knowledge_base,
                                        llm_provider=provider)
        ctx = ExecutionContext(task_description="anything", task_id="t1")
        result = skill.execute(ctx)

        assert result.output.content == {"handler": True}


class TestMockProviderMultiStep:
    def test_step_responses_sequence(self):
        provider = MockProvider(step_responses=[
            LLMResponse(intent="step1",
                        tool_calls=[ToolCall("search", {"q": "test"})]),
            LLMResponse(intent="step2", content={"result": "done"}),
        ])
        req = LLMRequest(task_description="t", skill_name="s",
                         skill_description="d")
        r1 = provider.generate(req)
        assert r1.intent == "step1"
        assert len(r1.tool_calls) == 1
        r2 = provider.generate(req)
        assert r2.intent == "step2"
        assert r2.content == {"result": "done"}

    def test_step_responses_last_repeats(self):
        provider = MockProvider(step_responses=[
            LLMResponse(content={"x": 1}),
        ])
        req = LLMRequest(task_description="t", skill_name="s",
                         skill_description="d")
        r1 = provider.generate(req)
        r2 = provider.generate(req)
        assert r1.content == r2.content

    def test_step_responses_empty_falls_back(self):
        provider = MockProvider(step_responses=[])
        req = LLMRequest(
            task_description="hello", skill_name="s", skill_description="d",
            templates={"g": {"match": ["hello"], "body": "Hi"}},
        )
        resp = provider.generate(req)
        assert resp.intent == "g"

    def test_existing_responses_dict_still_works(self):
        provider = MockProvider(
            responses={"generate": LLMResponse(intent="custom")})
        req = LLMRequest(task_description="t", skill_name="s",
                         skill_description="d")
        assert provider.generate(req).intent == "custom"


class TestMultiStepExecution:
    def test_loop_exits_on_no_tool_calls(self, sample_skill_with_templates,
                                         knowledge_base):
        """When LLM returns content without tool_calls, loop exits immediately."""
        provider = MockProvider()
        skill = SkillLoader._load_skill(
            sample_skill_with_templates, knowledge_base,
            llm_provider=provider)
        ctx = ExecutionContext(task_description="hello world", task_id="t1")
        result = skill.execute(ctx)
        assert result.success
        assert len(result.steps) == 0

    def test_multi_step_with_tools(self, sample_skill_dir, knowledge_base):
        """Simulate multi-step: LLM calls tool, gets result, calls again, done."""
        from tools import ToolRegistry, ToolDefinition
        registry = ToolRegistry()
        registry.register_custom_tool(
            ToolDefinition(name="greet", description="Greet someone"),
            lambda name="World": f"Hello, {name}!")

        provider = MockProvider(step_responses=[
            LLMResponse(tool_calls=[ToolCall("greet", {"name": "A"})]),
            LLMResponse(tool_calls=[ToolCall("greet", {"name": "B"})]),
            LLMResponse(intent="done", content={"result": "complete"}),
        ])
        skill = SkillLoader._load_skill(
            sample_skill_dir, knowledge_base,
            llm_provider=provider, tool_registry=registry)
        ctx = ExecutionContext(task_description="test", task_id="t1")
        result = skill.execute(ctx)
        assert result.success
        assert len(result.steps) == 2
        assert result.output.metadata.get('steps_taken') == 3

    def test_max_steps_enforced(self, sample_skill_dir, knowledge_base):
        """Loop stops at max_steps even if LLM keeps requesting tools."""
        from tools import ToolRegistry, ToolDefinition
        registry = ToolRegistry()
        registry.register_custom_tool(
            ToolDefinition(name="echo", description="Echo"),
            lambda msg="x": msg)

        # Provider always returns tool calls (never stops)
        provider = MockProvider(step_responses=[
            LLMResponse(tool_calls=[ToolCall("echo", {"msg": "x"})]),
        ])
        skill = SkillLoader._load_skill(
            sample_skill_dir, knowledge_base,
            llm_provider=provider, tool_registry=registry)
        ctx = ExecutionContext(task_description="test", task_id="t1")
        result = skill.execute(ctx)
        # Default max_steps is 5; all 5 steps should have tool calls
        assert len(result.steps) == 5

    def test_tool_error_triggers_recovery(self, sample_skill_dir,
                                          knowledge_base):
        """Tool failure triggers RECOVERY rules, LLM sees recovery info."""
        from tools import ToolRegistry, ToolDefinition

        registry = ToolRegistry()

        def failing_tool():
            raise ValueError("timezone not set for scheduling")

        registry.register_custom_tool(
            ToolDefinition(name="bad_tool", description="Fails"), failing_tool)

        # Add a RECOVERY rule for timezone errors
        rule = Rule(
            id="recovery_tz", name="Recover Timezone",
            rule_type=RuleType.RECOVERY,
            conditions=[Condition("context.has_timezone",
                                  ConditionOperator.EQUALS, False)],
            actions=[Action("add_field", "context.timezone", "UTC")],
            confidence=1.0, source_error_type="TimezoneError",
        )

        provider = MockProvider(step_responses=[
            LLMResponse(tool_calls=[ToolCall("bad_tool", {})]),
            LLMResponse(intent="recovered", content={"recovered": True}),
        ])
        skill = SkillLoader._load_skill(
            sample_skill_dir, knowledge_base,
            llm_provider=provider, tool_registry=registry)
        knowledge_base.add_rule(skill.name, rule)

        ctx = ExecutionContext(task_description="test at 2pm", task_id="t1",
                              has_timezone=False)
        result = skill.execute(ctx)
        assert result.success
        assert len(result.steps) == 1
        assert "recovery_tz" in result.steps[0].recovery_applied
        assert result.steps[0].errors  # tool error recorded

    def test_steps_recorded_in_result(self, sample_skill_dir, knowledge_base):
        """ExecutionResult.steps captures tool calls and results."""
        from tools import ToolRegistry, ToolDefinition

        registry = ToolRegistry()
        registry.register_custom_tool(
            ToolDefinition(name="add", description="Add numbers"),
            lambda a=0, b=0: a + b)

        provider = MockProvider(step_responses=[
            LLMResponse(tool_calls=[ToolCall("add", {"a": 1, "b": 2})]),
            LLMResponse(content={"sum": 3}),
        ])
        skill = SkillLoader._load_skill(
            sample_skill_dir, knowledge_base,
            llm_provider=provider, tool_registry=registry)
        ctx = ExecutionContext(task_description="test", task_id="t1")
        result = skill.execute(ctx)
        assert len(result.steps) == 1
        assert result.steps[0].tool_calls[0]['tool'] == 'add'
        assert result.steps[0].errors == []
