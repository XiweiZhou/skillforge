"""Tests for LearningEngine, PatternDetector, and ErrorRepository."""

import pytest
from datetime import datetime
from pathlib import Path

from learning import (
    LearningEngine, PatternDetector, ErrorRepository, SuccessRepository,
    ErrorRecord, StepErrorRecord, StepErrorRepository,
)
from knowledge import KnowledgeBase, RuleGenerator, RuleType


class TestErrorRepository:
    def test_record_and_retrieve(self, tmp_data_dir):
        repo = ErrorRepository(tmp_data_dir)
        repo.record(ErrorRecord(
            timestamp=datetime.now(),
            skill_name="email_writer",
            task_description="test email",
            error_type="TimezoneError",
            error_message="No timezone",
            context_snapshot={},
            rules_applied=[],
        ))
        errors = repo.get_by_skill("email_writer")
        assert len(errors) == 1
        assert errors[0].error_type == "TimezoneError"

    def test_get_by_type(self, tmp_data_dir):
        repo = ErrorRepository(tmp_data_dir)
        for i in range(3):
            repo.record(ErrorRecord(
                timestamp=datetime.now(),
                skill_name="s", task_description=f"t{i}",
                error_type="SpamTriggerError", error_message="spam",
                context_snapshot={}, rules_applied=[],
            ))
        repo.record(ErrorRecord(
            timestamp=datetime.now(),
            skill_name="s", task_description="t_other",
            error_type="TimezoneError", error_message="tz",
            context_snapshot={}, rules_applied=[],
        ))
        spam_errors = repo.get_by_type("SpamTriggerError")
        assert len(spam_errors) == 3

    def test_persistence(self, tmp_data_dir):
        repo = ErrorRepository(tmp_data_dir)
        repo.record(ErrorRecord(
            timestamp=datetime.now(),
            skill_name="s", task_description="t",
            error_type="E", error_message="m",
            context_snapshot={}, rules_applied=[],
        ))

        repo2 = ErrorRepository(tmp_data_dir)
        assert len(repo2.errors) == 1


class TestPatternDetector:
    def test_detect_frequent_pattern(self):
        detector = PatternDetector(min_frequency=3, min_confidence=0.3)
        errors = [
            ErrorRecord(timestamp=datetime.now(),
                        skill_name="s", task_description=f"task about time {i} pm",
                        error_type="TimezoneError", error_message="tz",
                        context_snapshot={"context": {"has_timezone": False}},
                        rules_applied=[])
            for i in range(5)
        ]
        patterns = detector.detect_patterns(errors)
        assert len(patterns) >= 1
        error_types = [p[0] for p in patterns]
        assert "TimezoneError" in error_types

    def test_no_pattern_below_frequency(self):
        detector = PatternDetector(min_frequency=5)
        errors = [
            ErrorRecord(timestamp=datetime.now(),
                        skill_name="s", task_description="t",
                        error_type="Rare", error_message="m",
                        context_snapshot={}, rules_applied=[])
            for _ in range(2)
        ]
        patterns = detector.detect_patterns(errors)
        assert len(patterns) == 0


class TestLearningEngine:
    def test_record_error(self, knowledge_base, tmp_data_dir):
        engine = LearningEngine(knowledge_base, tmp_data_dir)
        engine.record_error(
            skill_name="email_writer",
            task_description="test",
            error_type="TimezoneError",
            error_message="Missing timezone",
            context_snapshot={},
            rules_applied=[],
        )
        stats = engine.get_statistics()
        assert stats["total_errors"] > 0

    def test_record_success(self, knowledge_base, tmp_data_dir):
        engine = LearningEngine(knowledge_base, tmp_data_dir)
        engine.record_success(
            skill_name="email_writer",
            task_description="test",
            context_snapshot={},
            rules_applied=[],
            execution_time_ms=10.0,
        )
        stats = engine.get_statistics()
        assert stats["total_successes"] > 0

    def test_learning_cycle_generates_rules(self, knowledge_base, tmp_data_dir):
        engine = LearningEngine(knowledge_base, tmp_data_dir)

        # Record enough errors to trigger pattern detection
        for i in range(6):
            engine.record_error(
                skill_name="email_writer",
                task_description=f"email about meeting at {i+1} pm",
                error_type="TimezoneError",
                error_message="Timezone not specified",
                context_snapshot={"context": {"has_timezone": False}},
                rules_applied=[],
            )

        metrics = engine.run_learning_cycle(min_frequency=3, min_confidence=0.3)
        assert metrics.patterns_detected >= 1
        assert metrics.rules_generated >= 1

        # Verify rule was added to knowledge base
        rules = knowledge_base.get_rules("email_writer")
        assert len(rules) >= 1

    def test_clear_data(self, knowledge_base, tmp_data_dir):
        engine = LearningEngine(knowledge_base, tmp_data_dir)
        engine.record_error(
            skill_name="s", task_description="t",
            error_type="E", error_message="m",
            context_snapshot={}, rules_applied=[],
        )
        engine.clear_data()
        stats = engine.get_statistics()
        assert stats["total_errors"] == 0


class TestStepErrorRepository:
    def test_record_and_retrieve(self, tmp_data_dir):
        repo = StepErrorRepository(tmp_data_dir)
        repo.record(StepErrorRecord(
            timestamp=datetime.now(), skill_name="email_writer",
            task_description="test task", step_number=1,
            tool_name="web_search", error_type="TimezoneError",
            error_message="No timezone",
        ))
        assert len(repo.errors) == 1
        assert repo.errors[0].tool_name == "web_search"

    def test_persistence(self, tmp_data_dir):
        repo = StepErrorRepository(tmp_data_dir)
        repo.record(StepErrorRecord(
            timestamp=datetime.now(), skill_name="s",
            task_description="t", step_number=1,
            tool_name="tool", error_type="E", error_message="m",
        ))
        repo2 = StepErrorRepository(tmp_data_dir)
        assert len(repo2.errors) == 1

    def test_get_by_skill(self, tmp_data_dir):
        repo = StepErrorRepository(tmp_data_dir)
        repo.record(StepErrorRecord(
            timestamp=datetime.now(), skill_name="skill_a",
            task_description="t", step_number=1,
            tool_name="x", error_type="E", error_message="m",
        ))
        repo.record(StepErrorRecord(
            timestamp=datetime.now(), skill_name="skill_b",
            task_description="t", step_number=1,
            tool_name="x", error_type="E", error_message="m",
        ))
        assert len(repo.get_by_skill("skill_a")) == 1


class TestLearningEngineRecovery:
    def test_record_step_error(self, knowledge_base, tmp_data_dir):
        engine = LearningEngine(knowledge_base, tmp_data_dir)
        engine.record_step_error(
            skill_name="email_writer", task_description="test",
            step_number=1, tool_name="search",
            error_type="TimezoneError", error_message="Missing tz",
        )
        assert len(engine.step_error_repo.errors) == 1

    def test_clear_data_clears_step_errors(self, knowledge_base, tmp_data_dir):
        engine = LearningEngine(knowledge_base, tmp_data_dir)
        engine.record_step_error(
            skill_name="s", task_description="t",
            step_number=1, tool_name="x",
            error_type="E", error_message="m",
        )
        engine.clear_data()
        assert len(engine.step_error_repo.errors) == 0

    def test_learning_cycle_generates_recovery_rules(self, knowledge_base,
                                                      tmp_data_dir):
        engine = LearningEngine(knowledge_base, tmp_data_dir)
        for i in range(6):
            engine.record_step_error(
                skill_name="email_writer",
                task_description=f"email at {i} pm",
                step_number=1, tool_name="send_email",
                error_type="TimezoneError",
                error_message="Timezone missing",
            )
        metrics = engine.run_learning_cycle(min_frequency=3,
                                            min_confidence=0.3)
        rules = knowledge_base.get_rules("email_writer")
        recovery_rules = [r for r in rules
                          if r.rule_type == RuleType.RECOVERY]
        assert len(recovery_rules) >= 1
        assert metrics.rules_generated >= 1
