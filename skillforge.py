#!/usr/bin/env python3
"""
SkillForge - Self-Improving Agents with Closed-Loop Learning
Unified interface with declarative skill loading and knowledge application
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from knowledge import KnowledgeBase, RuleGenerator
from skills import SkillRegistry, ExecutionContext
from learning import LearningEngine, LearningMetrics
from tools import ToolRegistry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SkillForge")


@dataclass
class ForgeResult:
    """Result of a SkillForge execution"""
    task_id: str
    skill_name: str
    success: bool
    output: Any
    errors: List[str]
    warnings: List[str]
    rules_applied: List[str]
    execution_time_ms: float

    def __str__(self):
        status = "SUCCESS" if self.success else "FAILED"
        return f"[{status}] {self.skill_name}: {len(self.rules_applied)} rules, {self.execution_time_ms:.1f}ms"


class SkillForge:
    """
    Unified interface for self-improving task execution.

    Skills are loaded declaratively from SKILL.md files (AgentSkills.io spec).
    Knowledge rules influence execution via closed-loop learning.
    """

    def __init__(self,
                 data_dir: Optional[Path] = None,
                 skills_dir: Optional[Path] = None,
                 llm_provider=None):
        """
        Initialize SkillForge.

        Args:
            data_dir: Directory for learning data (default: ./data/learning)
            skills_dir: Directory containing skill definitions (default: ./skills)
            llm_provider: Optional LLM provider for intelligent execution.
                          When None, skills fall back to template-based execution.
        """
        self.data_dir = Path(data_dir or "./data/learning")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir = Path(skills_dir) if skills_dir else None
        self.llm_provider = llm_provider

        # Initialize knowledge base
        self.knowledge_base = KnowledgeBase(self.data_dir)

        # Initialize tool registry (shared across all skills)
        self.tool_registry = ToolRegistry()

        # Initialize skill registry (loads from skills/ directory)
        self.skill_registry = SkillRegistry(
            self.knowledge_base, self.skills_dir,
            llm_provider=self.llm_provider,
            tool_registry=self.tool_registry,
        )

        # Initialize learning engine
        self.learning_engine = LearningEngine(self.knowledge_base, self.data_dir)

        # Build error classification index from PATTERN_LIBRARY
        self._error_keywords = self._build_error_classification()

        # Statistics
        self.tasks_executed = 0
        self.tasks_succeeded = 0
        self.tasks_failed = 0

        logger.info(f"SkillForge initialized with {len(self.skill_registry.list_skills())} skills")

    def execute(self,
               task_description: str,
               skill_name: Optional[str] = None,
               context_overrides: Optional[Dict[str, Any]] = None) -> ForgeResult:
        """
        Execute a task with automatic skill selection and knowledge application

        Args:
            task_description: Natural language task description
            skill_name: Optional specific skill to use (otherwise auto-selected)
            context_overrides: Optional context values to set

        Returns:
            ForgeResult with execution details
        """
        self.tasks_executed += 1
        task_id = f"task_{self.tasks_executed}"

        # Select skill
        if skill_name:
            skill = self.skill_registry.get(skill_name)
        else:
            skill = self.skill_registry.get_for_task(task_description)

        if not skill:
            self.tasks_failed += 1
            return ForgeResult(
                task_id=task_id,
                skill_name="none",
                success=False,
                output=None,
                errors=["No suitable skill found"],
                warnings=[],
                rules_applied=[],
                execution_time_ms=0,
            )

        # Create execution context
        context = ExecutionContext(
            task_description=task_description,
            task_id=task_id,
        )

        # Apply overrides (routes to context.properties for dynamic fields)
        if context_overrides:
            for key, value in context_overrides.items():
                setattr(context, key, value)

        # Execute skill (this applies knowledge automatically)
        result = skill.execute(context)

        # Record outcome for learning
        if result.success:
            self.tasks_succeeded += 1
            self.learning_engine.record_success(
                skill_name=skill.name,
                task_description=task_description,
                context_snapshot=result.context_snapshot,
                rules_applied=result.rules_applied,
                execution_time_ms=result.execution_time_ms,
            )
        else:
            self.tasks_failed += 1
            for error in result.errors:
                # Determine error type from message
                error_type = self._classify_error(error)
                self.learning_engine.record_error(
                    skill_name=skill.name,
                    task_description=task_description,
                    error_type=error_type,
                    error_message=error,
                    context_snapshot=result.context_snapshot,
                    rules_applied=result.rules_applied,
                )

        # Record step-level errors for learning
        for step in result.steps:
            for error_msg in step.errors:
                error_type = self._classify_error(error_msg)
                tool_name = (step.tool_calls[0]['tool']
                             if step.tool_calls else 'unknown')
                self.learning_engine.record_step_error(
                    skill_name=skill.name,
                    task_description=task_description,
                    step_number=step.step_number,
                    tool_name=tool_name,
                    error_type=error_type,
                    error_message=error_msg,
                    recovery_applied=step.recovery_applied,
                    recovery_succeeded=result.success,
                    context_snapshot=result.context_snapshot,
                )

        return ForgeResult(
            task_id=task_id,
            skill_name=skill.name,
            success=result.success,
            output=result.output.content if result.output else None,
            errors=result.errors,
            warnings=result.warnings,
            rules_applied=result.rules_applied,
            execution_time_ms=result.execution_time_ms,
        )

    @staticmethod
    def _build_error_classification() -> Dict[str, str]:
        """Build keyword -> error_type index from the PATTERN_LIBRARY."""
        keywords = {}
        for error_type in RuleGenerator.PATTERN_LIBRARY:
            # Derive keywords from error type name (e.g. TimezoneError -> timezone)
            base = error_type.replace('Error', '').lower()
            keywords[base] = error_type
        # Add common aliases
        keywords.setdefault('spam', 'SpamTriggerError')
        keywords.setdefault('vague', 'PoorQueryError')
        keywords.setdefault('query', 'PoorQueryError')
        return keywords

    def _classify_error(self, error_message: str) -> str:
        """Classify error message using LLM provider or keyword fallback."""
        if self.llm_provider and self.llm_provider.is_available():
            known_types = list(set(self._error_keywords.values()))
            return self.llm_provider.classify_error(error_message, known_types)

        error_lower = error_message.lower()
        for keyword, error_type in self._error_keywords.items():
            if keyword in error_lower:
                return error_type
        return 'GenericError'

    def run_learning_cycle(self,
                          min_frequency: int = 3,
                          min_confidence: float = 0.5) -> LearningMetrics:
        """
        Run a learning cycle to detect patterns and generate rules

        Returns:
            LearningMetrics with cycle results
        """
        return self.learning_engine.run_learning_cycle(min_frequency, min_confidence)

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        learning_stats = self.learning_engine.get_statistics()
        kb_stats = self.knowledge_base.get_statistics()

        return {
            'execution': {
                'tasks_executed': self.tasks_executed,
                'tasks_succeeded': self.tasks_succeeded,
                'tasks_failed': self.tasks_failed,
                'success_rate': self.tasks_succeeded / self.tasks_executed if self.tasks_executed > 0 else 0,
            },
            'learning': learning_stats,
            'knowledge': kb_stats,
            'skills': {
                'available': self.skill_registry.list_skills(),
                'skill_stats': {
                    name: {
                        'executions': skill.executions,
                        'success_rate': skill.success_rate,
                    }
                    for name, skill in self.skill_registry.skills.items()
                }
            }
        }

    def print_statistics(self):
        """Print formatted statistics"""
        stats = self.get_statistics()

        print("\n" + "=" * 70)
        print("SKILLFORGE STATISTICS")
        print("=" * 70)

        print("\nExecution:")
        print(f"  Tasks executed: {stats['execution']['tasks_executed']}")
        print(f"  Success rate: {stats['execution']['success_rate']:.1%}")
        print(f"  Succeeded: {stats['execution']['tasks_succeeded']}")
        print(f"  Failed: {stats['execution']['tasks_failed']}")

        print("\nLearning:")
        print(f"  Learning cycles: {stats['learning']['learning_cycles']}")
        print(f"  Total rules: {stats['learning']['total_rules']}")
        print(f"  Rule applications: {stats['learning']['rule_applications']}")
        print(f"  Rule success rate: {stats['learning']['rule_success_rate']:.1%}")

        print("\nSkills:")
        for skill_name, skill_stats in stats['skills']['skill_stats'].items():
            print(f"  {skill_name}: {skill_stats['executions']} executions, "
                  f"{skill_stats['success_rate']:.1%} success")

        print("\nRules by Skill:")
        for skill_name, count in stats['knowledge']['rules_by_skill'].items():
            print(f"  {skill_name}: {count} rules")

        print("=" * 70 + "\n")

    def get_skill_rules(self, skill_name: str) -> List[str]:
        """Get human-readable list of rules for a skill"""
        rules = self.knowledge_base.get_rules(skill_name)
        return [str(rule) for rule in rules]

    def reset(self):
        """Reset all statistics and learning data"""
        self.tasks_executed = 0
        self.tasks_succeeded = 0
        self.tasks_failed = 0
        self.learning_engine.clear_data()

        # Re-initialize tool registry and skill registry to reset state
        self.tool_registry = ToolRegistry()
        self.skill_registry = SkillRegistry(
            self.knowledge_base, self.skills_dir,
            llm_provider=self.llm_provider,
            tool_registry=self.tool_registry,
        )


def main():
    """Demo of SkillForge"""
    forge = SkillForge()

    print("SkillForge Demo")
    print("-" * 40)

    # Execute some tasks
    tasks = [
        "Write an email about the meeting at 2 PM",
        "Schedule a meeting with the team",
        "Search for Python documentation",
    ]

    for task in tasks:
        result = forge.execute(task)
        print(f"\nTask: {task}")
        print(f"Result: {result}")
        print(f"Rules applied: {result.rules_applied}")

    # Run learning cycle
    print("\n" + "-" * 40)
    print("Running learning cycle...")
    metrics = forge.run_learning_cycle()
    print(f"Learning metrics: {metrics.to_dict()}")

    # Print statistics
    forge.print_statistics()


if __name__ == "__main__":
    main()
