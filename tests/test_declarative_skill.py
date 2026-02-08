"""Tests for DeclarativeSkill execution pipeline."""

import pytest
from pathlib import Path

from skills import (
    DeclarativeSkill, ExecutionContext, ExecutionResult, ExecutionStatus,
    SkillOutput, SkillLoader,
)
from knowledge import KnowledgeBase, Rule, RuleType, Condition, ConditionOperator, Action


class TestExecutionContext:
    def test_basic_creation(self):
        ctx = ExecutionContext(task_description="hello", task_id="t1")
        assert ctx.task_description == "hello"
        assert ctx.task_id == "t1"
        assert ctx.warnings == []
        assert ctx.flags == set()

    def test_dynamic_properties_via_kwargs(self):
        ctx = ExecutionContext(
            task_description="test", task_id="t1",
            has_timezone=False, has_attachment=True,
        )
        assert ctx.has_timezone is False
        assert ctx.has_attachment is True
        assert ctx.properties == {"has_timezone": False, "has_attachment": True}

    def test_dynamic_property_set_after_init(self):
        ctx = ExecutionContext(task_description="test", task_id="t1")
        ctx.custom_field = 42
        assert ctx.custom_field == 42
        assert ctx.properties["custom_field"] == 42

    def test_unknown_property_returns_none(self):
        ctx = ExecutionContext(task_description="test", task_id="t1")
        assert ctx.nonexistent is None

    def test_known_fields_not_in_properties(self):
        ctx = ExecutionContext(task_description="test", task_id="t1")
        ctx.warnings = ["warn"]
        assert "warnings" not in ctx.properties
        assert ctx.warnings == ["warn"]

    def test_to_dict_includes_properties(self):
        ctx = ExecutionContext(
            task_description="test", task_id="t1",
            has_timezone=False,
        )
        d = ctx.to_dict()
        assert d["context"]["has_timezone"] is False
        assert d["task"]["description"] == "test"

    def test_update_from_dict(self):
        ctx = ExecutionContext(task_description="test", task_id="t1")
        ctx.update_from_dict({
            "_applied_rules": ["r1"],
            "_flags": ["flag1"],
            "context": {"warnings": ["warn"]},
        })
        assert ctx.applied_rules == ["r1"]
        assert "flag1" in ctx.flags
        assert ctx.warnings == ["warn"]


class TestDeclarativeSkillExecution:
    def test_execute_with_templates(self, sample_skill_with_templates, knowledge_base):
        skill = SkillLoader._load_skill(sample_skill_with_templates, knowledge_base)
        ctx = ExecutionContext(task_description="hello world", task_id="t1")
        result = skill.execute(ctx)

        assert result.success
        assert result.output.output_type == "test_output"
        assert result.output.content["subject"] == "Greeting"

    def test_execute_matches_farewell_template(self, sample_skill_with_templates, knowledge_base):
        skill = SkillLoader._load_skill(sample_skill_with_templates, knowledge_base)
        ctx = ExecutionContext(task_description="goodbye everyone", task_id="t1")
        result = skill.execute(ctx)

        assert result.success
        assert result.output.content["subject"] == "Farewell"

    def test_execute_falls_back_to_default(self, sample_skill_with_templates, knowledge_base):
        skill = SkillLoader._load_skill(sample_skill_with_templates, knowledge_base)
        ctx = ExecutionContext(task_description="completely unrelated task", task_id="t1")
        result = skill.execute(ctx)

        assert result.success
        # Falls back to last template (default)
        assert result.output.content["subject"] == "Default"

    def test_execute_without_templates(self, sample_skill_dir, knowledge_base):
        skill = SkillLoader._load_skill(sample_skill_dir, knowledge_base)
        ctx = ExecutionContext(task_description="do something", task_id="t1")
        result = skill.execute(ctx)

        assert result.success
        assert "content" in result.output.content

    def test_knowledge_rules_applied(self, sample_skill_dir, knowledge_base):
        """Rules in KnowledgeBase are applied during execution."""
        skill = SkillLoader._load_skill(sample_skill_dir, knowledge_base)

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

    def test_execution_records_timing(self, sample_skill_dir, knowledge_base):
        skill = SkillLoader._load_skill(sample_skill_dir, knowledge_base)
        ctx = ExecutionContext(task_description="test", task_id="t1")
        result = skill.execute(ctx)
        assert result.execution_time_ms >= 0

    def test_execution_tracks_statistics(self, sample_skill_dir, knowledge_base):
        skill = SkillLoader._load_skill(sample_skill_dir, knowledge_base)
        assert skill.executions == 0

        ctx = ExecutionContext(task_description="test", task_id="t1")
        skill.execute(ctx)
        assert skill.executions == 1
        assert skill.successes == 1


class TestDeclarativeSkillValidation:
    def test_attachment_validation_fails(self, sample_skill_dir, knowledge_base):
        """Attachment flag + no attachment = failure."""
        skill = SkillLoader._load_skill(sample_skill_dir, knowledge_base)
        ctx = ExecutionContext(task_description="test", task_id="t1", has_attachment=False)
        ctx.flags.add("attachment_mentioned")
        result = skill.execute(ctx)
        assert not result.success
        assert any("attachment" in e.lower() for e in result.errors)

    def test_conflict_validation_fails(self, sample_skill_dir, knowledge_base):
        """Scheduling conflict flag + has_conflict = failure."""
        skill = SkillLoader._load_skill(sample_skill_dir, knowledge_base)
        ctx = ExecutionContext(task_description="test", task_id="t1", has_conflict=True)
        ctx.flags.add("scheduling_conflict")
        result = skill.execute(ctx)
        assert not result.success


class TestCustomHandler:
    def test_custom_handler_takes_priority(self, tmp_skills_dir, knowledge_base):
        """skills/test-handler/scripts/handler.py should override declarative execution."""
        skill_dir = tmp_skills_dir / "handler-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: handler-skill\n"
            "description: Skill with custom handler.\n"
            "---\n"
            "# Handler Skill\n"
        )
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "handler.py").write_text(
            "from skills import ExecutionResult, ExecutionStatus, SkillOutput\n"
            "\n"
            "def execute(context, metadata):\n"
            "    return ExecutionResult(\n"
            "        status=ExecutionStatus.SUCCESS,\n"
            "        output=SkillOutput(content={'custom': True}, output_type='custom'),\n"
            "    )\n"
        )

        skill = SkillLoader._load_skill(skill_dir, knowledge_base)
        ctx = ExecutionContext(task_description="anything", task_id="t1")
        result = skill.execute(ctx)

        assert result.success
        assert result.output.content == {"custom": True}
        assert result.output.output_type == "custom"
