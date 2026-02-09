"""Tests for KnowledgeBase, Rule, Condition, Action, and RuleGenerator."""

import json
import pytest
from pathlib import Path

from knowledge import (
    Condition, ConditionOperator, Action, Rule, RuleType,
    KnowledgeBase, RuleGenerator,
)


class TestCondition:
    def test_equals_match(self):
        cond = Condition("context.has_timezone", ConditionOperator.EQUALS, False)
        ctx = {"context": {"has_timezone": False}}
        assert cond.evaluate(ctx) is True

    def test_equals_no_match(self):
        cond = Condition("context.has_timezone", ConditionOperator.EQUALS, True)
        ctx = {"context": {"has_timezone": False}}
        assert cond.evaluate(ctx) is False

    def test_matches_regex(self):
        cond = Condition("task.description", ConditionOperator.MATCHES, r"\d+\s*pm")
        ctx = {"task": {"description": "meeting at 2 pm"}}
        assert cond.evaluate(ctx) is True

    def test_contains(self):
        cond = Condition("task.description", ConditionOperator.CONTAINS, "urgent")
        ctx = {"task": {"description": "this is urgent"}}
        assert cond.evaluate(ctx) is True

    def test_less_than(self):
        cond = Condition("context.avg_credibility", ConditionOperator.LESS_THAN, 0.5)
        ctx = {"context": {"avg_credibility": 0.3}}
        assert cond.evaluate(ctx) is True

    def test_nested_field_missing(self):
        cond = Condition("context.nonexistent", ConditionOperator.EQUALS, True)
        ctx = {"context": {}}
        assert cond.evaluate(ctx) is False


class TestAction:
    def test_flag_action(self):
        action = Action("flag", "_flags", "timezone_added")
        ctx = {"_flags": []}
        result = action.apply(ctx)
        assert "timezone_added" in result["_flags"]

    def test_add_field(self):
        action = Action("add_field", "context.timezone", "UTC")
        ctx = {"context": {}}
        result = action.apply(ctx)
        assert result["context"]["timezone"] == "UTC"

    def test_append(self):
        action = Action("append", "context.warnings", "Watch out")
        ctx = {"context": {"warnings": []}}
        result = action.apply(ctx)
        assert "Watch out" in result["context"]["warnings"]


class TestRule:
    def test_rule_matches(self):
        rule = Rule(
            id="r1",
            name="Test",
            rule_type=RuleType.PREVENTION,
            conditions=[Condition("context.val", ConditionOperator.EQUALS, True)],
            actions=[Action("flag", "_flags", "matched")],
        )
        ctx = {"context": {"val": True}, "_flags": []}
        assert rule.matches(ctx) is True

    def test_rule_no_match(self):
        rule = Rule(
            id="r1",
            name="Test",
            rule_type=RuleType.PREVENTION,
            conditions=[Condition("context.val", ConditionOperator.EQUALS, True)],
            actions=[],
        )
        ctx = {"context": {"val": False}}
        assert rule.matches(ctx) is False

    def test_rule_apply(self):
        rule = Rule(
            id="r1",
            name="Test",
            rule_type=RuleType.PREVENTION,
            conditions=[Condition("context.val", ConditionOperator.EQUALS, True)],
            actions=[Action("flag", "_flags", "done")],
        )
        ctx = {"context": {"val": True}, "_flags": []}
        result = rule.apply(ctx)
        assert "done" in result["_flags"]

    def test_rule_confidence_updates(self):
        rule = Rule(id="r1", name="Test", rule_type=RuleType.PREVENTION,
                    conditions=[], actions=[], confidence=0.5)
        # rule.apply() increments times_applied; record_outcome tracks success
        rule.apply({})
        rule.record_outcome(True)
        assert rule.times_applied == 1
        assert rule.times_successful == 1
        rule.apply({})
        rule.record_outcome(False)
        assert rule.times_applied == 2
        assert rule.times_successful == 1


class TestKnowledgeBase:
    def test_add_and_get_rules(self, knowledge_base):
        rule = Rule(id="r1", name="Test", rule_type=RuleType.PREVENTION,
                    conditions=[], actions=[])
        knowledge_base.add_rule("email_writer", rule)
        rules = knowledge_base.get_rules("email_writer")
        assert len(rules) == 1
        assert rules[0].id == "r1"

    def test_apply_rules(self, knowledge_base):
        rule = Rule(
            id="r1", name="Test", rule_type=RuleType.PREVENTION,
            conditions=[Condition("context.x", ConditionOperator.EQUALS, True)],
            actions=[Action("flag", "_flags", "applied")],
            confidence=1.0,
        )
        knowledge_base.add_rule("skill", rule)
        ctx = {"context": {"x": True}, "_flags": [], "_applied_rules": []}
        result = knowledge_base.apply_rules("skill", ctx)
        assert "applied" in result["_flags"]
        assert "r1" in result["_applied_rules"]

    def test_save_and_load_rules(self, tmp_data_dir):
        kb = KnowledgeBase(tmp_data_dir)
        rule = Rule(id="persist", name="Persist", rule_type=RuleType.PREVENTION,
                    conditions=[], actions=[])
        kb.add_rule("test_skill", rule)
        kb.save_rules()

        kb2 = KnowledgeBase(tmp_data_dir)
        rules = kb2.get_rules("test_skill")
        assert len(rules) == 1
        assert rules[0].id == "persist"

    def test_get_statistics(self, knowledge_base):
        stats = knowledge_base.get_statistics()
        assert "total_rules" in stats
        assert "rules_by_skill" in stats


class TestRuleGenerator:
    def test_pattern_library_has_common_patterns(self):
        assert "TimezoneError" in RuleGenerator.PATTERN_LIBRARY
        assert "SpamTriggerError" in RuleGenerator.PATTERN_LIBRARY
        assert "ConflictError" in RuleGenerator.PATTERN_LIBRARY

    def test_generate_rule_from_known_error(self):
        gen = RuleGenerator()
        rule = gen.generate_rule_from_error("TimezoneError", frequency=5, confidence=0.8)
        assert rule is not None
        assert rule.rule_type == RuleType.PREVENTION
        assert rule.confidence == 0.8
        assert len(rule.conditions) > 0
        assert len(rule.actions) > 0

    def test_generate_rule_from_unknown_error(self):
        gen = RuleGenerator()
        rule = gen.generate_rule_from_error("UnknownError", frequency=5, confidence=0.8)
        assert rule is None

    def test_generate_custom_rule(self):
        gen = RuleGenerator()
        rule = gen.generate_custom_rule(
            name="Custom",
            conditions=[{"field": "context.x", "operator": "equals", "value": True}],
            actions=[{"action_type": "flag", "target": "_flags", "value": "custom"}],
        )
        assert rule is not None
        assert rule.name == "Custom"


class TestRecoveryRuleType:
    def test_recovery_in_enum(self):
        assert RuleType.RECOVERY.value == "recovery"

    def test_recovery_serialization(self):
        rule = Rule(id="r1", name="Test Recovery", rule_type=RuleType.RECOVERY,
                    conditions=[], actions=[], confidence=0.8)
        d = rule.to_dict()
        assert d['rule_type'] == 'recovery'
        restored = Rule.from_dict(d)
        assert restored.rule_type == RuleType.RECOVERY

    def test_generate_recovery_rule(self):
        gen = RuleGenerator()
        rule = gen.generate_recovery_rule_from_error("TimezoneError", 5, 0.8)
        assert rule is not None
        assert rule.rule_type == RuleType.RECOVERY
        assert "Recover" in rule.name

    def test_no_recovery_for_unknown_error(self):
        gen = RuleGenerator()
        rule = gen.generate_recovery_rule_from_error("UnknownError", 5, 0.8)
        assert rule is None

    def test_no_recovery_for_pattern_without_recovery_section(self):
        gen = RuleGenerator()
        rule = gen.generate_recovery_rule_from_error("PreferenceError", 5, 0.8)
        assert rule is None

    def test_get_recovery_actions(self, knowledge_base):
        rule = Rule(
            id="rec1", name="Recover TZ", rule_type=RuleType.RECOVERY,
            conditions=[Condition("context.has_timezone", ConditionOperator.EQUALS, False)],
            actions=[Action("add_field", "context.timezone", "UTC")],
            confidence=1.0,
        )
        knowledge_base.add_rule("email_writer", rule)
        ctx = {"context": {"has_timezone": False}}
        result = knowledge_base.get_recovery_actions("email_writer", ctx)
        assert result["context"]["timezone"] == "UTC"
