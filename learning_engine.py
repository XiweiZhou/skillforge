#!/usr/bin/env python3
"""
SkillForge Learning Engine
Handles error tracking, pattern detection, and skill knowledge updates
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from collections import defaultdict

logger = logging.getLogger("LearningEngine")


class KnowledgeType(Enum):
    """Type of knowledge learned"""
    PATTERN = "pattern"
    ERROR_AVOIDANCE = "error_avoidance"
    BEST_PRACTICE = "best_practice"
    OPTIMIZATION = "optimization"


@dataclass
class ErrorEvent:
    """Error recorded during execution"""
    timestamp: datetime
    skill_name: str
    task_description: str
    error_type: str
    error_message: str
    recovery_successful: bool = False
    recovery_method: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'skill': self.skill_name,
            'task': self.task_description,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'recovery_successful': self.recovery_successful,
            'recovery_method': self.recovery_method,
        }


@dataclass
class SuccessPattern:
    """Successful task execution"""
    timestamp: datetime
    skill_name: str
    task_description: str
    duration: float
    outputs_generated: int

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'skill': self.skill_name,
            'task': self.task_description,
            'duration': duration,
            'outputs': self.outputs_generated,
        }


@dataclass
class KnowledgeItem:
    """Learned knowledge item"""
    title: str
    knowledge_type: KnowledgeType
    description: str
    confidence: float
    frequency: int
    learned_from_errors: int = 0
    learned_from_successes: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'title': self.title,
            'type': self.knowledge_type.value,
            'description': self.description,
            'confidence': self.confidence,
            'frequency': self.frequency,
            'from_errors': self.learned_from_errors,
            'from_successes': self.learned_from_successes,
        }


class ErrorRepository:
    """Repository for error events"""

    def __init__(self, data_dir: Path):
        """
        Initialize error repository

        Args:
            data_dir: Directory for storing error data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.errors_file = self.data_dir / "errors.jsonl"
        self.errors: List[ErrorEvent] = []

        self._load_errors()

    def _load_errors(self):
        """Load errors from storage"""
        if self.errors_file.exists():
            try:
                with open(self.errors_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            # Note: Simplified loading, timestamp as string
                            self.errors.append(ErrorEvent(
                                timestamp=datetime.fromisoformat(data['timestamp']),
                                skill_name=data['skill'],
                                task_description=data['task'],
                                error_type=data['error_type'],
                                error_message=data['error_message'],
                                recovery_successful=data.get('recovery_successful', False),
                                recovery_method=data.get('recovery_method'),
                            ))
            except Exception as e:
                logger.error(f"Error loading errors from {self.errors_file}: {e}")

    def record_error(self, error: ErrorEvent):
        """Record an error event"""
        self.errors.append(error)

        # Append to file
        try:
            with open(self.errors_file, 'a') as f:
                f.write(json.dumps(error.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Error writing to {self.errors_file}: {e}")

    def get_errors_by_skill(self, skill_name: str) -> List[ErrorEvent]:
        """Get all errors for a skill"""
        return [e for e in self.errors if e.skill_name == skill_name]

    def get_errors_by_type(self, error_type: str) -> List[ErrorEvent]:
        """Get all errors of a type"""
        return [e for e in self.errors if e.error_type == error_type]

    def get_recent_errors(self, skill_name: str, count: int = 20) -> List[ErrorEvent]:
        """Get recent errors for a skill"""
        skill_errors = self.get_errors_by_skill(skill_name)
        return skill_errors[-count:]


class SuccessRepository:
    """Repository for success events"""

    def __init__(self, data_dir: Path):
        """
        Initialize success repository

        Args:
            data_dir: Directory for storing success data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.successes_file = self.data_dir / "successes.jsonl"
        self.successes: List[SuccessPattern] = []

        self._load_successes()

    def _load_successes(self):
        """Load successes from storage"""
        if self.successes_file.exists():
            try:
                with open(self.successes_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            self.successes.append(SuccessPattern(
                                timestamp=datetime.fromisoformat(data['timestamp']),
                                skill_name=data['skill'],
                                task_description=data['task'],
                                duration=data.get('duration', 0),
                                outputs_generated=data.get('outputs', 0),
                            ))
            except Exception as e:
                logger.error(f"Error loading successes from {self.successes_file}: {e}")

    def record_success(self, success: SuccessPattern):
        """Record a success event"""
        self.successes.append(success)

        # Append to file
        try:
            with open(self.successes_file, 'a') as f:
                f.write(json.dumps(success.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Error writing to {self.successes_file}: {e}")

    def get_successes_by_skill(self, skill_name: str) -> List[SuccessPattern]:
        """Get all successes for a skill"""
        return [s for s in self.successes if s.skill_name == skill_name]


class PatternAnalyzer:
    """Analyzes errors and successes to detect patterns"""

    def __init__(self):
        """Initialize pattern analyzer"""
        pass

    def detect_patterns(self,
                       errors: List[ErrorEvent],
                       min_frequency: int = 5,
                       min_confidence: float = 0.60) -> List[Tuple[str, float, int]]:
        """
        Detect recurring error patterns

        Args:
            errors: List of error events
            min_frequency: Minimum occurrences to consider a pattern
            min_confidence: Minimum confidence score (0-1)

        Returns:
            List of (pattern_description, confidence, frequency)
        """
        if not errors:
            return []

        # Count error types
        error_counts = defaultdict(int)
        for error in errors:
            error_counts[error.error_type] += 1

        # Calculate confidence and filter
        patterns = []
        total_errors = len(errors)

        for error_type, count in error_counts.items():
            if count >= min_frequency:
                confidence = count / total_errors
                if confidence >= min_confidence:
                    patterns.append((error_type, confidence, count))

        # Sort by frequency descending
        patterns.sort(key=lambda x: x[2], reverse=True)

        return patterns

    def suggest_knowledge_item(self,
                              pattern: Tuple[str, float, int],
                              errors: List[ErrorEvent]) -> KnowledgeItem:
        """
        Suggest a knowledge item from an error pattern

        Args:
            pattern: (error_type, confidence, frequency)
            errors: List of error events for context

        Returns:
            KnowledgeItem
        """
        error_type, confidence, frequency = pattern

        # Get sample errors of this type
        matching_errors = [e for e in errors if e.error_type == error_type]

        # Create knowledge item
        title = self._generate_title(error_type)
        description = self._generate_description(error_type, matching_errors)

        return KnowledgeItem(
            title=title,
            knowledge_type=KnowledgeType.ERROR_AVOIDANCE,
            description=description,
            confidence=confidence,
            frequency=frequency,
            learned_from_errors=frequency,
        )

    def _generate_title(self, error_type: str) -> str:
        """Generate human-readable title from error type"""
        # Convert error type to title case
        return error_type.replace('Error', '').replace('_', ' ').title()

    def _generate_description(self, error_type: str, errors: List[ErrorEvent]) -> str:
        """Generate description from error examples"""
        if not errors:
            return f"Learned to avoid {error_type}"

        # Use first error message as example
        sample_message = errors[0].error_message

        return f"Pattern detected: {error_type}. Example: {sample_message}"


class KnowledgeRepository:
    """Repository for learned knowledge items"""

    def __init__(self, data_dir: Path):
        """
        Initialize knowledge repository

        Args:
            data_dir: Directory for storing knowledge data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.knowledge_file = self.data_dir / "learned_knowledge.json"
        self.learned_knowledge: Dict[str, List[KnowledgeItem]] = defaultdict(list)

        self._load_knowledge()

    def _load_knowledge(self):
        """Load knowledge from storage"""
        if self.knowledge_file.exists():
            try:
                data = json.loads(self.knowledge_file.read_text())
                for skill_name, items in data.items():
                    for item_dict in items:
                        item = KnowledgeItem(
                            title=item_dict['title'],
                            knowledge_type=KnowledgeType(item_dict['type']),
                            description=item_dict['description'],
                            confidence=item_dict['confidence'],
                            frequency=item_dict['frequency'],
                            learned_from_errors=item_dict.get('from_errors', 0),
                            learned_from_successes=item_dict.get('from_successes', 0),
                        )
                        self.learned_knowledge[skill_name].append(item)
            except Exception as e:
                logger.error(f"Error loading knowledge from {self.knowledge_file}: {e}")

    def save_knowledge(self):
        """Save knowledge to storage"""
        try:
            data = {}
            for skill_name, items in self.learned_knowledge.items():
                data[skill_name] = [item.to_dict() for item in items]

            self.knowledge_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Error saving knowledge to {self.knowledge_file}: {e}")

    def add_knowledge(self, skill_name: str, item: KnowledgeItem):
        """Add a knowledge item for a skill"""
        # Check if similar item exists
        for existing in self.learned_knowledge[skill_name]:
            if existing.title == item.title:
                # Update existing item
                existing.frequency += item.frequency
                existing.confidence = (existing.confidence + item.confidence) / 2
                return

        # Add new item
        self.learned_knowledge[skill_name].append(item)

    def get_learned_knowledge(self, skill_name: str) -> List[KnowledgeItem]:
        """Get all knowledge items for a skill"""
        return self.learned_knowledge.get(skill_name, [])

    def get_total_knowledge_items(self) -> int:
        """Get total count of knowledge items"""
        return sum(len(items) for items in self.learned_knowledge.values())


class SkillUpdater:
    """Updates skill files with learned knowledge"""

    def __init__(self, skills_base_path: Path):
        """
        Initialize skill updater

        Args:
            skills_base_path: Base path for skills
        """
        self.skills_base_path = Path(skills_base_path)

    def update_skill_knowledge(self, skill_name: str, knowledge_items: List[KnowledgeItem]):
        """
        Update skill file with learned knowledge

        Args:
            skill_name: Name of the skill
            knowledge_items: List of KnowledgeItem to add
        """
        skill_dir = self.skills_base_path / skill_name
        skill_file = skill_dir / "SKILL.md"

        if not skill_file.exists():
            logger.warning(f"Skill file not found: {skill_file}")
            return

        try:
            content = skill_file.read_text()

            # Find the learned knowledge section
            if "## Learned Knowledge" not in content:
                # Add section if doesn't exist
                content += "\n## Learned Knowledge\n<!-- This section auto-updated by LearningEngine -->\n\n"

            # Find insertion point
            knowledge_marker = "## Learned Knowledge\n<!-- This section auto-updated by LearningEngine -->\n"
            if knowledge_marker in content:
                # Insert after the comment
                insertion_point = content.find(knowledge_marker) + len(knowledge_marker)
            else:
                # Fallback to just after the marker
                insertion_point = content.find("## Learned Knowledge") + len("## Learned Knowledge\n")

            # Build knowledge text
            knowledge_text = ""
            for item in knowledge_items:
                knowledge_text += (
                    f"### {item.title} (confidence: {item.confidence:.2f}, frequency: {item.frequency})\n"
                    f"{item.description}\n\n"
                )

            # Insert knowledge items
            content = content[:insertion_point] + knowledge_text + content[insertion_point:]

            skill_file.write_text(content)
            logger.info(f"Updated skill file: {skill_file} with {len(knowledge_items)} items")

        except Exception as e:
            logger.error(f"Error updating skill file {skill_file}: {e}")


class LearningEngine:
    """Main learning engine for SkillForge"""

    def __init__(self,
                 skills_dir: Path,
                 data_dir: Path):
        """
        Initialize learning engine

        Args:
            skills_dir: Directory containing skills
            data_dir: Directory for learning data storage
        """
        self.skills_dir = Path(skills_dir)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize repositories
        self.error_repo = ErrorRepository(self.data_dir)
        self.success_repo = SuccessRepository(self.data_dir)
        self.repository = KnowledgeRepository(self.data_dir)

        # Initialize tools
        self.analyzer = PatternAnalyzer()
        self.skill_updater = SkillUpdater(self.skills_dir)

        # Learning thresholds
        self.error_threshold = 10  # Trigger learning after 10 errors
        self.success_threshold = 50  # Trigger learning after 50 successes
        self.task_threshold = 50  # Trigger learning after 50 tasks

        logger.info("LearningEngine initialized")

    def record_task_error(self,
                         task,
                         error: Exception,
                         step: str = "EXECUTION",
                         recovery_successful: bool = False,
                         recovery_method: Optional[str] = None):
        """
        Record a task error

        Args:
            task: Task object
            error: Exception object
            step: Where error occurred
            recovery_successful: Whether recovery worked
            recovery_method: How it was recovered
        """
        # Determine skill and error type
        skill_name = task.selected_skills[0].name if task.selected_skills else "unknown"
        error_type = error.__class__.__name__

        event = ErrorEvent(
            timestamp=datetime.now(),
            skill_name=skill_name,
            task_description=task.description,
            error_type=error_type,
            error_message=str(error),
            recovery_successful=recovery_successful,
            recovery_method=recovery_method,
        )

        self.error_repo.record_error(event)
        logger.debug(f"Recorded error for {skill_name}: {error_type}")

    def record_task_success(self, result):
        """
        Record a successful task execution

        Args:
            result: ExecutionResult object
        """
        for skill in result.selected_skills:
            success = SuccessPattern(
                timestamp=datetime.now(),
                skill_name=skill.name,
                task_description="",  # Would get from result
                duration=result.duration,
                outputs_generated=len(result.outputs),
            )

            self.success_repo.record_success(success)

    def run_learning_cycle(self,
                          min_frequency: int = 5,
                          min_confidence: float = 0.60) -> Dict[str, int]:
        """
        Manually run a learning cycle

        Args:
            min_frequency: Minimum pattern frequency
            min_confidence: Minimum pattern confidence

        Returns:
            Statistics about what was learned
        """
        logger.info("Running learning cycle...")
        stats = {
            'patterns_detected': 0,
            'knowledge_items_added': 0,
            'skills_updated': 0,
        }

        # Get all errors by skill
        all_errors = self.error_repo.errors
        errors_by_skill = defaultdict(list)

        for error in all_errors:
            errors_by_skill[error.skill_name].append(error)

        # Analyze patterns for each skill
        for skill_name, errors in errors_by_skill.items():
            if not errors:
                continue

            # Detect patterns
            patterns = self.analyzer.detect_patterns(
                errors,
                min_frequency=min_frequency,
                min_confidence=min_confidence
            )

            if patterns:
                stats['patterns_detected'] += len(patterns)

                # Generate knowledge items
                knowledge_items = []
                for pattern in patterns:
                    item = self.analyzer.suggest_knowledge_item(pattern, errors)
                    knowledge_items.append(item)
                    self.repository.add_knowledge(skill_name, item)

                if knowledge_items:
                    stats['knowledge_items_added'] += len(knowledge_items)

                    # Update skill file
                    self.skill_updater.update_skill_knowledge(skill_name, knowledge_items)
                    stats['skills_updated'] += 1

                    logger.info(
                        f"Skill {skill_name}: detected {len(patterns)} patterns, "
                        f"added {len(knowledge_items)} knowledge items"
                    )

        # Save knowledge repository
        self.repository.save_knowledge()

        logger.info(f"Learning cycle complete: {stats}")
        return stats

    def get_learning_stats(self) -> Dict[str, Any]:
        """
        Get statistics about learning

        Returns:
            Dictionary with learning statistics
        """
        total_errors = len(self.error_repo.errors)
        total_successes = len(self.success_repo.successes)
        total_knowledge = self.repository.get_total_knowledge_items()

        # Recovery rate
        recovery_count = sum(
            1 for e in self.error_repo.errors if e.recovery_successful
        )
        recovery_rate = recovery_count / total_errors if total_errors > 0 else 0

        # Skills with knowledge
        skills_with_knowledge = len([
            skill for skill in self.repository.learned_knowledge
            if self.repository.learned_knowledge[skill]
        ])

        return {
            'total_errors': total_errors,
            'total_successes': total_successes,
            'recovery_rate': recovery_rate,
            'skills_with_learned_knowledge': skills_with_knowledge,
            'total_knowledge_items': total_knowledge,
        }


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    data_dir = Path("./data/learning")
    engine = LearningEngine(
        skills_dir=Path("/mnt/skills"),
        data_dir=data_dir
    )

    # Create sample error
    class SampleTask:
        def __init__(self):
            self.description = "Write an email"
            self.selected_skills = [type('Skill', (), {'name': 'email_writer'})()]

    task = SampleTask()
    error = ValueError("Email marked as spam")

    engine.record_task_error(task, error)

    # Run learning cycle
    stats = engine.run_learning_cycle()
    print(f"Learning stats: {stats}")
