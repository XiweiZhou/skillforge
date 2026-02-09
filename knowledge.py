#!/usr/bin/env python3
"""
SkillForge Knowledge System
Actionable knowledge representation with rules, conditions, and actions
"""

import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger("Knowledge")


class RuleType(Enum):
    """Types of learned rules"""
    PREVENTION = "prevention"      # Prevent errors before they happen
    VALIDATION = "validation"      # Validate output before returning
    TRANSFORMATION = "transformation"  # Transform input/output
    OPTIMIZATION = "optimization"  # Improve efficiency
    RECOVERY = "recovery"          # Mid-execution error recovery


class ConditionOperator(Enum):
    """Operators for rule conditions"""
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES = "matches"
    EQUALS = "equals"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"


@dataclass
class Condition:
    """A single condition in a rule"""
    field: str                      # What to check: "task.description", "context.timezone", etc.
    operator: ConditionOperator     # How to check
    value: Any                      # What to compare against

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate this condition against a context"""
        # Navigate nested fields like "task.description"
        field_value = self._get_field_value(context, self.field)

        if field_value is None:
            return False

        if self.operator == ConditionOperator.CONTAINS:
            if isinstance(field_value, str):
                return self.value.lower() in field_value.lower()
            elif isinstance(field_value, (list, set)):
                return self.value in field_value
            return False

        elif self.operator == ConditionOperator.NOT_CONTAINS:
            if isinstance(field_value, str):
                return self.value.lower() not in field_value.lower()
            elif isinstance(field_value, (list, set)):
                return self.value not in field_value
            return True

        elif self.operator == ConditionOperator.MATCHES:
            if isinstance(field_value, str):
                return bool(re.search(self.value, field_value, re.IGNORECASE))
            return False

        elif self.operator == ConditionOperator.EQUALS:
            return field_value == self.value

        elif self.operator == ConditionOperator.GREATER_THAN:
            return field_value > self.value

        elif self.operator == ConditionOperator.LESS_THAN:
            return field_value < self.value

        return False

    def _get_field_value(self, context: Dict, field_path: str) -> Any:
        """Navigate nested field path like 'task.description'"""
        parts = field_path.split('.')
        current = context

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                return None

            if current is None:
                return None

        return current

    def to_dict(self) -> Dict:
        return {
            'field': self.field,
            'operator': self.operator.value,
            'value': self.value
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Condition':
        return cls(
            field=data['field'],
            operator=ConditionOperator(data['operator']),
            value=data['value']
        )

    def __str__(self) -> str:
        return f"{self.field} {self.operator.value} '{self.value}'"


@dataclass
class Action:
    """An action to take when conditions are met"""
    action_type: str           # "add_field", "transform", "flag", "reject"
    target: str                # What to modify: "output.timezone", "context.warnings"
    value: Any                 # New value or transformation spec

    def apply(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply this action to a context, return modified context"""
        result = context.copy()

        if self.action_type == "add_field":
            self._set_field_value(result, self.target, self.value)

        elif self.action_type == "append":
            current = self._get_field_value(result, self.target) or []
            if isinstance(current, list):
                current.append(self.value)
                self._set_field_value(result, self.target, current)

        elif self.action_type == "flag":
            flags = result.get('_flags', set())
            if isinstance(flags, list):
                flags = set(flags)
            flags.add(self.value)
            result['_flags'] = flags

        elif self.action_type == "transform":
            current = self._get_field_value(result, self.target)
            if current and isinstance(current, str):
                # Simple replacement transform
                if isinstance(self.value, dict) and 'pattern' in self.value:
                    new_value = re.sub(
                        self.value['pattern'],
                        self.value.get('replacement', ''),
                        current
                    )
                    self._set_field_value(result, self.target, new_value)

        elif self.action_type == "reject":
            result['_rejected'] = True
            result['_rejection_reason'] = self.value

        return result

    def _get_field_value(self, context: Dict, field_path: str) -> Any:
        parts = field_path.split('.')
        current = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _set_field_value(self, context: Dict, field_path: str, value: Any):
        parts = field_path.split('.')
        current = context
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def to_dict(self) -> Dict:
        return {
            'action_type': self.action_type,
            'target': self.target,
            'value': self.value
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Action':
        return cls(
            action_type=data['action_type'],
            target=data['target'],
            value=data['value']
        )

    def __str__(self) -> str:
        return f"{self.action_type}({self.target} = {self.value})"


@dataclass
class Rule:
    """A learned rule with conditions and actions"""
    id: str
    name: str
    rule_type: RuleType
    conditions: List[Condition]
    actions: List[Action]

    # Learning metadata
    source_error_type: str = ""
    confidence: float = 0.0
    times_applied: int = 0
    times_successful: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_applied: Optional[datetime] = None

    # For human readability
    description: str = ""

    @property
    def effectiveness(self) -> float:
        """Calculate how effective this rule has been"""
        if self.times_applied == 0:
            return self.confidence  # Use initial confidence if never applied
        return self.times_successful / self.times_applied

    def matches(self, context: Dict[str, Any]) -> bool:
        """Check if all conditions match the context"""
        return all(cond.evaluate(context) for cond in self.conditions)

    def apply(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all actions to the context"""
        result = context.copy()
        for action in self.actions:
            result = action.apply(result)

        # Track application
        self.times_applied += 1
        self.last_applied = datetime.now()

        # Add metadata about which rule was applied
        applied_rules = result.get('_applied_rules', [])
        applied_rules.append(self.id)
        result['_applied_rules'] = applied_rules

        return result

    def record_outcome(self, successful: bool):
        """Record the outcome of applying this rule"""
        if successful:
            self.times_successful += 1
        # Recalculate confidence with Bayesian update
        self.confidence = (self.confidence * 0.7) + (self.effectiveness * 0.3)

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'rule_type': self.rule_type.value,
            'conditions': [c.to_dict() for c in self.conditions],
            'actions': [a.to_dict() for a in self.actions],
            'source_error_type': self.source_error_type,
            'confidence': self.confidence,
            'times_applied': self.times_applied,
            'times_successful': self.times_successful,
            'created_at': self.created_at.isoformat(),
            'last_applied': self.last_applied.isoformat() if self.last_applied else None,
            'description': self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Rule':
        return cls(
            id=data['id'],
            name=data['name'],
            rule_type=RuleType(data['rule_type']),
            conditions=[Condition.from_dict(c) for c in data['conditions']],
            actions=[Action.from_dict(a) for a in data['actions']],
            source_error_type=data.get('source_error_type', ''),
            confidence=data.get('confidence', 0.0),
            times_applied=data.get('times_applied', 0),
            times_successful=data.get('times_successful', 0),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            last_applied=datetime.fromisoformat(data['last_applied']) if data.get('last_applied') else None,
            description=data.get('description', ''),
        )

    def __str__(self) -> str:
        conds = " AND ".join(str(c) for c in self.conditions)
        acts = ", ".join(str(a) for a in self.actions)
        return f"IF ({conds}) THEN ({acts}) [conf={self.confidence:.2f}]"


class KnowledgeBase:
    """
    Central knowledge store with rules indexed by skill
    Supports rule application, learning feedback, and persistence
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.rules_file = self.data_dir / "rules.json"
        self.rules_by_skill: Dict[str, List[Rule]] = defaultdict(list)
        self.rule_index: Dict[str, Rule] = {}  # id -> Rule

        self._load_rules()

    def _load_rules(self):
        """Load rules from storage"""
        if self.rules_file.exists():
            try:
                data = json.loads(self.rules_file.read_text())
                for skill_name, rules_data in data.items():
                    for rule_data in rules_data:
                        rule = Rule.from_dict(rule_data)
                        self.rules_by_skill[skill_name].append(rule)
                        self.rule_index[rule.id] = rule
                logger.info(f"Loaded {len(self.rule_index)} rules from storage")
            except Exception as e:
                logger.error(f"Error loading rules: {e}")

    def save_rules(self):
        """Persist rules to storage"""
        try:
            data = {}
            for skill_name, rules in self.rules_by_skill.items():
                data[skill_name] = [rule.to_dict() for rule in rules]
            self.rules_file.write_text(json.dumps(data, indent=2))
            logger.debug(f"Saved {len(self.rule_index)} rules to storage")
        except Exception as e:
            logger.error(f"Error saving rules: {e}")

    def add_rule(self, skill_name: str, rule: Rule):
        """Add a new rule for a skill"""
        # Check for duplicate
        for existing in self.rules_by_skill[skill_name]:
            if existing.id == rule.id:
                # Update existing
                existing.confidence = max(existing.confidence, rule.confidence)
                return

        self.rules_by_skill[skill_name].append(rule)
        self.rule_index[rule.id] = rule
        logger.info(f"Added rule '{rule.name}' for skill '{skill_name}'")

    def get_rules(self, skill_name: str, min_confidence: float = 0.0) -> List[Rule]:
        """Get all rules for a skill above confidence threshold"""
        rules = self.rules_by_skill.get(skill_name, [])
        return [r for r in rules if r.confidence >= min_confidence]

    def get_applicable_rules(self, skill_name: str, context: Dict[str, Any],
                            min_confidence: float = 0.3) -> List[Rule]:
        """Get rules that match the given context"""
        rules = self.get_rules(skill_name, min_confidence)
        applicable = [r for r in rules if r.matches(context)]
        # Sort by confidence descending
        applicable.sort(key=lambda r: r.confidence, reverse=True)
        return applicable

    def apply_rules(self, skill_name: str, context: Dict[str, Any],
                   rule_types: Optional[List[RuleType]] = None) -> Dict[str, Any]:
        """
        Apply all applicable rules to a context
        Returns modified context with _applied_rules metadata
        """
        result = context.copy()
        if '_applied_rules' not in result:
            result['_applied_rules'] = []

        applicable = self.get_applicable_rules(skill_name, result)

        if rule_types:
            applicable = [r for r in applicable if r.rule_type in rule_types]

        for rule in applicable:
            result = rule.apply(result)
            logger.debug(f"Applied rule: {rule.name}")

        return result

    def get_recovery_actions(self, skill_name: str,
                             context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply RECOVERY rules and return the modified context."""
        return self.apply_rules(skill_name, context,
                                rule_types=[RuleType.RECOVERY])

    def record_rule_outcome(self, rule_id: str, successful: bool):
        """Record whether a rule application was successful"""
        if rule_id in self.rule_index:
            self.rule_index[rule_id].record_outcome(successful)

    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        total_rules = len(self.rule_index)
        total_applications = sum(r.times_applied for r in self.rule_index.values())
        total_successes = sum(r.times_successful for r in self.rule_index.values())

        by_skill = {
            skill: len(rules) for skill, rules in self.rules_by_skill.items()
        }

        avg_confidence = (
            sum(r.confidence for r in self.rule_index.values()) / total_rules
            if total_rules > 0 else 0
        )

        return {
            'total_rules': total_rules,
            'total_applications': total_applications,
            'total_successes': total_successes,
            'success_rate': total_successes / total_applications if total_applications > 0 else 0,
            'average_confidence': avg_confidence,
            'rules_by_skill': by_skill,
        }


class RuleGenerator:
    """
    Generates actionable rules from error patterns.

    PATTERN_LIBRARY is a generic collection of common error patterns shared
    across all skills. Skills don't declare their own patterns -- the engine
    matches patterns to skills based on runtime errors. New patterns added
    here benefit every skill automatically.
    """

    # Generic pattern library -- backbone intelligence, not per-skill config
    PATTERN_LIBRARY = {
        'TimezoneError': {
            'detection': [
                Condition('task.description', ConditionOperator.MATCHES, r'\d{1,2}\s*(am|pm|AM|PM)'),
                Condition('context.has_timezone', ConditionOperator.EQUALS, False),
            ],
            'remediation': [
                Action('add_field', 'context.timezone', 'UTC'),
                Action('flag', '_flags', 'timezone_added'),
            ],
            'recovery': [
                Action('add_field', 'context.timezone', 'UTC'),
                Action('append', 'context.warnings', 'Timezone was missing; defaulted to UTC during recovery'),
            ],
            'description': 'Add timezone when time is mentioned without one'
        },
        'SpamTriggerError': {
            'detection': [
                Condition('task.description', ConditionOperator.MATCHES,
                         r'\b(free|urgent|limited time|act now|exclusive)\b'),
            ],
            'remediation': [
                Action('flag', '_flags', 'potential_spam'),
                Action('append', 'context.warnings', 'Contains spam trigger words'),
            ],
            'recovery': [
                Action('append', 'context.warnings', 'Spam trigger detected during execution; content may need review'),
            ],
            'description': 'Flag content with spam trigger words for review'
        },
        'AttachmentError': {
            'detection': [
                Condition('task.description', ConditionOperator.MATCHES,
                         r'\b(attach|attached|attachment|document|file)\b'),
                Condition('context.has_attachment', ConditionOperator.EQUALS, False),
            ],
            'remediation': [
                Action('flag', '_flags', 'attachment_mentioned'),
                Action('append', 'context.warnings', 'Attachment mentioned but not provided'),
            ],
            'recovery': [
                Action('append', 'context.warnings', 'Attachment reference detected in tool error; continuing without attachment'),
            ],
            'description': 'Warn when attachment is mentioned but not provided'
        },
        'ConflictError': {
            'detection': [
                Condition('context.has_conflict', ConditionOperator.EQUALS, True),
            ],
            'remediation': [
                Action('flag', '_flags', 'scheduling_conflict'),
                Action('append', 'context.warnings', 'Scheduling conflict detected'),
            ],
            'recovery': [
                Action('append', 'context.warnings', 'Scheduling conflict encountered during execution; suggest alternative time'),
            ],
            'description': 'Flag scheduling conflicts'
        },
        'PreferenceError': {
            'detection': [
                Condition('context.violates_preferences', ConditionOperator.EQUALS, True),
            ],
            'remediation': [
                Action('flag', '_flags', 'preference_violation'),
                Action('append', 'context.suggestions', 'Consider participant preferences'),
            ],
            'description': 'Warn when participant preferences are violated'
        },
        'PoorQueryError': {
            'detection': [
                Condition('task.description', ConditionOperator.MATCHES, r'^(what|how|why|when)\s+\w+\??$'),
            ],
            'remediation': [
                Action('flag', '_flags', 'vague_query'),
                Action('append', 'context.suggestions', 'Query may be too vague, consider adding specifics'),
            ],
            'recovery': [
                Action('append', 'context.suggestions', 'Query was too vague for tool; consider refining search terms'),
            ],
            'description': 'Flag overly simple or vague queries'
        },
        'LowCredibilityError': {
            'detection': [
                Condition('context.avg_credibility', ConditionOperator.LESS_THAN, 0.5),
            ],
            'remediation': [
                Action('flag', '_flags', 'low_credibility_sources'),
                Action('append', 'context.warnings', 'Sources have low credibility scores'),
            ],
            'recovery': [
                Action('append', 'context.warnings', 'Low credibility sources detected during search; filtering results'),
            ],
            'description': 'Warn about low credibility sources'
        },
    }

    def __init__(self):
        self._rule_counter = 0

    def _generate_rule_id(self, error_type: str) -> str:
        """Generate unique rule ID"""
        self._rule_counter += 1
        return f"rule_{error_type.lower()}_{self._rule_counter}"

    def generate_rule_from_error(self, error_type: str,
                                  frequency: int,
                                  confidence: float) -> Optional[Rule]:
        """
        Generate an actionable rule from an error pattern

        Args:
            error_type: Type of error (e.g., 'TimezoneError')
            frequency: How many times this error occurred
            confidence: Confidence in the pattern (0-1)

        Returns:
            Rule object or None if no rule can be generated
        """
        if error_type not in self.PATTERN_LIBRARY:
            logger.warning(f"No pattern template for error type: {error_type}")
            return None

        pattern = self.PATTERN_LIBRARY[error_type]

        rule = Rule(
            id=self._generate_rule_id(error_type),
            name=f"Prevent {error_type.replace('Error', '')}",
            rule_type=RuleType.PREVENTION,
            conditions=pattern['detection'].copy(),
            actions=pattern['remediation'].copy(),
            source_error_type=error_type,
            confidence=confidence,
            description=pattern['description'],
        )

        return rule

    def generate_recovery_rule_from_error(self, error_type: str,
                                           frequency: int,
                                           confidence: float) -> Optional[Rule]:
        """Generate a RECOVERY rule from a PATTERN_LIBRARY entry's recovery section."""
        if error_type not in self.PATTERN_LIBRARY:
            return None
        pattern = self.PATTERN_LIBRARY[error_type]
        if 'recovery' not in pattern:
            return None

        return Rule(
            id=self._generate_rule_id(f"{error_type}_recovery"),
            name=f"Recover {error_type.replace('Error', '')}",
            rule_type=RuleType.RECOVERY,
            conditions=pattern['detection'].copy(),
            actions=pattern['recovery'].copy(),
            source_error_type=error_type,
            confidence=confidence,
            description=f"Recovery: {pattern['description']}",
        )

    def generate_custom_rule(self,
                            name: str,
                            conditions: List[Dict],
                            actions: List[Dict],
                            rule_type: RuleType = RuleType.PREVENTION,
                            confidence: float = 0.5) -> Rule:
        """Generate a custom rule from specifications"""
        self._rule_counter += 1

        return Rule(
            id=f"custom_rule_{self._rule_counter}",
            name=name,
            rule_type=rule_type,
            conditions=[Condition.from_dict(c) for c in conditions],
            actions=[Action.from_dict(a) for a in actions],
            confidence=confidence,
        )


# Convenience functions
def create_knowledge_base(data_dir: str = "./data/learning") -> KnowledgeBase:
    """Create a knowledge base with default settings"""
    return KnowledgeBase(Path(data_dir))


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    kb = KnowledgeBase(Path("./data/learning"))
    generator = RuleGenerator()

    # Generate a rule from error pattern
    rule = generator.generate_rule_from_error("TimezoneError", frequency=5, confidence=0.75)
    if rule:
        kb.add_rule("email_writer", rule)
        print(f"Generated rule: {rule}")

    # Test rule matching
    context = {
        'task': {'description': 'Send email about meeting at 2 PM'},
        'context': {'has_timezone': False}
    }

    applicable = kb.get_applicable_rules("email_writer", context)
    print(f"Applicable rules: {len(applicable)}")

    if applicable:
        result = kb.apply_rules("email_writer", context)
        print(f"After applying rules: {result.get('_flags', set())}")

    kb.save_rules()
    print("Rules saved successfully")
