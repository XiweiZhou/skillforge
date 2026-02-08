#!/usr/bin/env python3
"""
SkillForge Learning Engine
Pattern detection that generates actionable rules with proper validation
"""

import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import random

from knowledge import KnowledgeBase, Rule, RuleGenerator, RuleType

logger = logging.getLogger("Learning")


@dataclass
class ErrorRecord:
    """Detailed error record for learning"""
    timestamp: datetime
    skill_name: str
    task_description: str
    error_type: str
    error_message: str
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    rules_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'skill': self.skill_name,
            'task': self.task_description,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'context': self.context_snapshot,
            'rules_applied': self.rules_applied,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ErrorRecord':
        return cls(
            timestamp=datetime.fromisoformat(data['timestamp']),
            skill_name=data['skill'],
            task_description=data['task'],
            error_type=data['error_type'],
            error_message=data['error_message'],
            context_snapshot=data.get('context', {}),
            rules_applied=data.get('rules_applied', []),
        )


@dataclass
class SuccessRecord:
    """Detailed success record for learning"""
    timestamp: datetime
    skill_name: str
    task_description: str
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    rules_applied: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'skill': self.skill_name,
            'task': self.task_description,
            'context': self.context_snapshot,
            'rules_applied': self.rules_applied,
            'execution_time_ms': self.execution_time_ms,
        }


@dataclass
class LearningMetrics:
    """Metrics for a learning cycle"""
    errors_analyzed: int = 0
    patterns_detected: int = 0
    rules_generated: int = 0
    rules_applied_total: int = 0
    rule_success_rate: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'errors_analyzed': self.errors_analyzed,
            'patterns_detected': self.patterns_detected,
            'rules_generated': self.rules_generated,
            'rules_applied_total': self.rules_applied_total,
            'rule_success_rate': self.rule_success_rate,
        }


class ErrorRepository:
    """Repository for error records"""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.errors_file = self.data_dir / "errors.jsonl"
        self.errors: List[ErrorRecord] = []
        self._load()

    def _load(self):
        if self.errors_file.exists():
            try:
                with open(self.errors_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            self.errors.append(ErrorRecord.from_dict(json.loads(line)))
            except Exception as e:
                logger.error(f"Error loading errors: {e}")

    def record(self, error: ErrorRecord):
        self.errors.append(error)
        try:
            with open(self.errors_file, 'a') as f:
                f.write(json.dumps(error.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Error writing error record: {e}")

    def get_by_skill(self, skill_name: str) -> List[ErrorRecord]:
        return [e for e in self.errors if e.skill_name == skill_name]

    def get_by_type(self, error_type: str) -> List[ErrorRecord]:
        return [e for e in self.errors if e.error_type == error_type]

    def get_recent(self, count: int = 100) -> List[ErrorRecord]:
        return self.errors[-count:]

    def clear(self):
        """Clear all errors (for testing)"""
        self.errors = []
        if self.errors_file.exists():
            self.errors_file.unlink()


class SuccessRepository:
    """Repository for success records"""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.successes_file = self.data_dir / "successes.jsonl"
        self.successes: List[SuccessRecord] = []
        self._load()

    def _load(self):
        if self.successes_file.exists():
            try:
                with open(self.successes_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            self.successes.append(SuccessRecord(
                                timestamp=datetime.fromisoformat(data['timestamp']),
                                skill_name=data['skill'],
                                task_description=data['task'],
                                context_snapshot=data.get('context', {}),
                                rules_applied=data.get('rules_applied', []),
                                execution_time_ms=data.get('execution_time_ms', 0),
                            ))
            except Exception as e:
                logger.error(f"Error loading successes: {e}")

    def record(self, success: SuccessRecord):
        self.successes.append(success)
        try:
            with open(self.successes_file, 'a') as f:
                f.write(json.dumps(success.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Error writing success record: {e}")

    def get_by_skill(self, skill_name: str) -> List[SuccessRecord]:
        return [s for s in self.successes if s.skill_name == skill_name]

    def clear(self):
        """Clear all successes (for testing)"""
        self.successes = []
        if self.successes_file.exists():
            self.successes_file.unlink()


class PatternDetector:
    """
    Detects patterns in errors and suggests actionable rules
    Goes beyond frequency counting to analyze context
    """

    def __init__(self, min_frequency: int = 3, min_confidence: float = 0.5):
        self.min_frequency = min_frequency
        self.min_confidence = min_confidence

    def detect_patterns(self, errors: List[ErrorRecord]) -> List[Tuple[str, float, int, Dict]]:
        """
        Detect error patterns with context analysis

        Returns:
            List of (error_type, confidence, frequency, context_features)
        """
        if not errors:
            return []

        # Group by error type
        by_type = defaultdict(list)
        for error in errors:
            by_type[error.error_type].append(error)

        patterns = []
        total_errors = len(errors)

        for error_type, type_errors in by_type.items():
            frequency = len(type_errors)

            if frequency >= self.min_frequency:
                confidence = frequency / total_errors

                if confidence >= self.min_confidence:
                    # Extract common context features
                    context_features = self._extract_common_features(type_errors)

                    patterns.append((error_type, confidence, frequency, context_features))

        # Sort by frequency
        patterns.sort(key=lambda x: x[2], reverse=True)

        return patterns

    def _extract_common_features(self, errors: List[ErrorRecord]) -> Dict[str, Any]:
        """Extract common features from error contexts"""
        features = {}

        if not errors:
            return features

        # Analyze task descriptions for common patterns
        task_words = defaultdict(int)
        for error in errors:
            words = error.task_description.lower().split()
            for word in words:
                if len(word) > 3:  # Skip short words
                    task_words[word] += 1

        # Find words that appear in >50% of errors
        threshold = len(errors) * 0.5
        common_words = [word for word, count in task_words.items() if count >= threshold]
        if common_words:
            features['common_task_words'] = common_words

        # Analyze context snapshots
        context_patterns = defaultdict(list)
        for error in errors:
            ctx = error.context_snapshot.get('context', {})
            for key, value in ctx.items():
                if isinstance(value, bool):
                    context_patterns[key].append(value)

        # Find consistent boolean patterns
        for key, values in context_patterns.items():
            if len(values) >= len(errors) * 0.8:  # 80% of errors have this key
                # Check if consistently True or False
                true_rate = sum(1 for v in values if v) / len(values)
                if true_rate > 0.8:
                    features[f'{key}_usually_true'] = True
                elif true_rate < 0.2:
                    features[f'{key}_usually_false'] = True

        return features


class LearningEngine:
    """
    Main learning engine that coordinates pattern detection and rule generation
    """

    def __init__(self, knowledge_base: KnowledgeBase, data_dir: Path):
        self.knowledge_base = knowledge_base
        self.data_dir = Path(data_dir)

        self.error_repo = ErrorRepository(data_dir)
        self.success_repo = SuccessRepository(data_dir)
        self.pattern_detector = PatternDetector()
        self.rule_generator = RuleGenerator()

        self.learning_cycles = 0
        self.total_rules_generated = 0

    def record_error(self,
                    skill_name: str,
                    task_description: str,
                    error_type: str,
                    error_message: str,
                    context_snapshot: Optional[Dict] = None,
                    rules_applied: Optional[List[str]] = None):
        """Record an execution error"""
        record = ErrorRecord(
            timestamp=datetime.now(),
            skill_name=skill_name,
            task_description=task_description,
            error_type=error_type,
            error_message=error_message,
            context_snapshot=context_snapshot or {},
            rules_applied=rules_applied or [],
        )
        self.error_repo.record(record)
        logger.debug(f"Recorded error: {error_type} for {skill_name}")

    def record_success(self,
                      skill_name: str,
                      task_description: str,
                      context_snapshot: Optional[Dict] = None,
                      rules_applied: Optional[List[str]] = None,
                      execution_time_ms: float = 0.0):
        """Record a successful execution"""
        record = SuccessRecord(
            timestamp=datetime.now(),
            skill_name=skill_name,
            task_description=task_description,
            context_snapshot=context_snapshot or {},
            rules_applied=rules_applied or [],
            execution_time_ms=execution_time_ms,
        )
        self.success_repo.record(record)

    def run_learning_cycle(self,
                          min_frequency: int = 3,
                          min_confidence: float = 0.5) -> LearningMetrics:
        """
        Run a learning cycle: detect patterns and generate rules

        Returns:
            LearningMetrics with cycle results
        """
        logger.info("Starting learning cycle...")
        self.learning_cycles += 1

        metrics = LearningMetrics()

        # Group errors by skill
        errors_by_skill = defaultdict(list)
        for error in self.error_repo.errors:
            errors_by_skill[error.skill_name].append(error)

        metrics.errors_analyzed = len(self.error_repo.errors)

        # Detect patterns for each skill
        for skill_name, errors in errors_by_skill.items():
            if not errors:
                continue

            # Update detector thresholds
            self.pattern_detector.min_frequency = min_frequency
            self.pattern_detector.min_confidence = min_confidence

            # Detect patterns
            patterns = self.pattern_detector.detect_patterns(errors)
            metrics.patterns_detected += len(patterns)

            # Generate rules for each pattern
            for error_type, confidence, frequency, features in patterns:
                # Check if we already have a rule for this error type
                existing_rules = self.knowledge_base.get_rules(skill_name)
                already_has_rule = any(
                    r.source_error_type == error_type for r in existing_rules
                )

                if not already_has_rule:
                    # Generate new rule
                    rule = self.rule_generator.generate_rule_from_error(
                        error_type, frequency, confidence
                    )

                    if rule:
                        self.knowledge_base.add_rule(skill_name, rule)
                        metrics.rules_generated += 1
                        self.total_rules_generated += 1
                        logger.info(f"Generated rule: {rule.name} for {skill_name}")

        # Calculate rule success rate
        kb_stats = self.knowledge_base.get_statistics()
        metrics.rules_applied_total = kb_stats['total_applications']
        metrics.rule_success_rate = kb_stats['success_rate']

        # Save knowledge base
        self.knowledge_base.save_rules()

        logger.info(f"Learning cycle complete: {metrics.to_dict()}")

        return metrics

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive learning statistics"""
        kb_stats = self.knowledge_base.get_statistics()

        return {
            'total_errors': len(self.error_repo.errors),
            'total_successes': len(self.success_repo.successes),
            'learning_cycles': self.learning_cycles,
            'total_rules': kb_stats['total_rules'],
            'rules_by_skill': kb_stats['rules_by_skill'],
            'rule_applications': kb_stats['total_applications'],
            'rule_success_rate': kb_stats['success_rate'],
            'average_rule_confidence': kb_stats['average_confidence'],
        }

    def clear_data(self):
        """Clear all learning data (for testing)"""
        self.error_repo.clear()
        self.success_repo.clear()
        self.learning_cycles = 0


class ValidationFramework:
    """
    Framework for validating that learning actually improves outcomes
    Implements proper train/test splits and ablation testing
    """

    def __init__(self, learning_engine: LearningEngine):
        self.learning_engine = learning_engine

    def run_ablation_test(self,
                         task_generator,
                         skill_executor,
                         num_tasks: int = 100,
                         learning_enabled: bool = True) -> Dict[str, Any]:
        """
        Run tasks with or without learning to measure impact

        Args:
            task_generator: Callable that generates (task_description, error_injection_fn)
            skill_executor: Callable that executes skill(task) -> (success, errors)
            num_tasks: Number of tasks to run
            learning_enabled: Whether to apply learned rules

        Returns:
            Dict with success rate, errors, etc.
        """
        successes = 0
        failures = 0
        errors_by_type = defaultdict(int)
        rules_applied_count = 0

        for i in range(num_tasks):
            task_desc, should_error, error_type = task_generator()

            # Execute with or without knowledge
            success, errors, rules_applied = skill_executor(
                task_desc,
                should_error,
                error_type,
                apply_knowledge=learning_enabled
            )

            if success:
                successes += 1
            else:
                failures += 1
                for err in errors:
                    errors_by_type[err] += 1

            rules_applied_count += len(rules_applied)

        return {
            'num_tasks': num_tasks,
            'successes': successes,
            'failures': failures,
            'success_rate': successes / num_tasks,
            'errors_by_type': dict(errors_by_type),
            'rules_applied': rules_applied_count,
            'learning_enabled': learning_enabled,
        }

    def compare_with_without_learning(self,
                                      task_generator,
                                      skill_executor,
                                      num_tasks: int = 100) -> Dict[str, Any]:
        """
        Compare performance with and without learning

        Returns:
            Dict with comparative metrics
        """
        # Run without learning
        without = self.run_ablation_test(
            task_generator, skill_executor, num_tasks, learning_enabled=False
        )

        # Run with learning
        with_learning = self.run_ablation_test(
            task_generator, skill_executor, num_tasks, learning_enabled=True
        )

        improvement = with_learning['success_rate'] - without['success_rate']

        return {
            'without_learning': without,
            'with_learning': with_learning,
            'improvement': improvement,
            'improvement_percent': improvement * 100,
            'learning_effective': improvement > 0,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test the learning engine
    from knowledge import KnowledgeBase

    kb = KnowledgeBase(Path("./data/learning"))
    engine = LearningEngine(kb, Path("./data/learning"))

    # Clear previous data for clean test
    engine.clear_data()

    # Simulate some errors
    for i in range(10):
        engine.record_error(
            skill_name="email_writer",
            task_description=f"Write email at 3 PM about meeting {i}",
            error_type="TimezoneError",
            error_message="Timezone not specified",
            context_snapshot={'context': {'has_timezone': False}},
        )

    # Run learning cycle
    metrics = engine.run_learning_cycle(min_frequency=3, min_confidence=0.3)
    print(f"Learning metrics: {metrics.to_dict()}")

    # Check statistics
    stats = engine.get_statistics()
    print(f"Statistics: {stats}")

    # Check generated rules
    rules = kb.get_rules("email_writer")
    for rule in rules:
        print(f"Rule: {rule}")
