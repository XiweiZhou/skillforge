"""Integration tests: full loop from execution through learning to improvement."""

import pytest
from pathlib import Path

from skillforge import SkillForge


@pytest.fixture
def forge(tmp_path):
    """SkillForge instance using the project's real skills."""
    data_dir = tmp_path / "data" / "learning"
    data_dir.mkdir(parents=True)
    real_skills = Path(__file__).parent.parent / "skills"
    return SkillForge(data_dir=data_dir, skills_dir=real_skills)


class TestFullLoop:
    def test_execute_email_task(self, forge):
        result = forge.execute("Write an email about the project update")
        assert result.success
        assert result.skill_name == "email_writer"
        assert result.output is not None

    def test_execute_calendar_task(self, forge):
        result = forge.execute("Schedule a meeting with the team")
        assert result.success
        assert result.skill_name == "calendar_manager"

    def test_execute_search_task(self, forge):
        result = forge.execute("Search for Python documentation")
        assert result.success
        assert result.skill_name == "web_searcher"

    def test_no_skill_found(self, forge):
        result = forge.execute("do something completely unknown xyz123")
        assert not result.success
        assert result.skill_name == "none"

    def test_learning_cycle_after_errors(self, forge):
        """Record errors, run learning, verify rules generated."""
        # Record enough timezone errors
        for i in range(6):
            forge.learning_engine.record_error(
                skill_name="email_writer",
                task_description=f"email about meeting at {i+1} pm",
                error_type="TimezoneError",
                error_message="Timezone not specified",
                context_snapshot={"context": {"has_timezone": False}},
                rules_applied=[],
            )

        metrics = forge.run_learning_cycle(min_frequency=3, min_confidence=0.3)
        assert metrics.rules_generated >= 1

        # Verify rules exist in knowledge base
        rules = forge.knowledge_base.get_rules("email_writer")
        assert len(rules) >= 1

    def test_rules_applied_during_execution(self, forge):
        """After learning, rules should be applied during execution."""
        # Add a rule manually
        from knowledge import Rule, RuleType, Condition, ConditionOperator, Action
        rule = Rule(
            id="test_tz_rule", name="Prevent Timezone",
            rule_type=RuleType.PREVENTION,
            conditions=[
                Condition("task.description", ConditionOperator.MATCHES, r"\d+\s*(am|pm)"),
                Condition("context.has_timezone", ConditionOperator.EQUALS, False),
            ],
            actions=[
                Action("add_field", "context.timezone", "UTC"),
                Action("flag", "_flags", "timezone_added"),
            ],
            confidence=1.0,
        )
        forge.knowledge_base.add_rule("email_writer", rule)

        result = forge.execute(
            "Write an email about the meeting at 2 pm",
            context_overrides={"has_timezone": False},
        )
        assert result.success
        assert "test_tz_rule" in result.rules_applied

    def test_statistics(self, forge):
        forge.execute("Write an email about project update")
        stats = forge.get_statistics()
        assert stats["execution"]["tasks_executed"] == 1
        assert "email_writer" in stats["skills"]["skill_stats"]

    def test_reset(self, forge):
        forge.execute("Write an email")
        assert forge.tasks_executed == 1
        forge.reset()
        assert forge.tasks_executed == 0

    def test_error_classification(self, forge):
        """Verify _classify_error uses PATTERN_LIBRARY keywords."""
        assert forge._classify_error("Timezone not set") == "TimezoneError"
        assert forge._classify_error("Spam detected in email") == "SpamTriggerError"
        assert forge._classify_error("Scheduling conflict found") == "ConflictError"
        assert forge._classify_error("totally unknown error") == "GenericError"
