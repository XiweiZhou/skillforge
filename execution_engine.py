#!/usr/bin/env python3
"""
SkillForge Execution Engine
Handles skill discovery, task analysis, and execution with error tracking
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import json

logger = logging.getLogger("ExecutionEngine")


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class ExecutionStatus(Enum):
    """Execution status values"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class ExecutionConfig:
    """Configuration for execution engine"""
    SKILLS_BASE_PATH: Path = Path("/mnt/skills")
    TIMEOUT_SECONDS: int = 300
    MAX_RETRIES: int = 3
    ENABLE_RECOVERY: bool = True
    LOG_LEVEL: str = "INFO"

    def __post_init__(self):
        if isinstance(self.SKILLS_BASE_PATH, str):
            self.SKILLS_BASE_PATH = Path(self.SKILLS_BASE_PATH)


@dataclass
class Skill:
    """Skill definition"""
    name: str
    description: str
    category: str
    triggers: List[str]
    file_types: List[str] = field(default_factory=list)
    version: str = "1.0"
    learned_knowledge: List[Dict] = field(default_factory=list)

    def matches_task(self, task_description: str) -> float:
        """
        Calculate skill relevance to task (0.0 to 1.0)
        Returns confidence score
        """
        task_lower = task_description.lower()

        # Check trigger words
        matches = sum(1 for trigger in self.triggers if trigger.lower() in task_lower)
        if matches == 0:
            return 0.0

        # Confidence based on number of triggers that match
        confidence = min(matches / len(self.triggers), 1.0) if self.triggers else 0.0
        return confidence


@dataclass
class Task:
    """Task definition"""
    id: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    user_files: Optional[List[str]] = None
    created_at: datetime = field(default_factory=datetime.now)
    selected_skills: List[Skill] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())[:8]


@dataclass
class ExecutionResult:
    """Result of task execution"""
    id: str
    task_id: str
    status: ExecutionStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    outputs: List[Path] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    selected_skills: List[Skill] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """Duration in seconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class SkillScanner:
    """Discovers and loads skills from filesystem"""

    def __init__(self, base_path: Path):
        """
        Initialize skill scanner

        Args:
            base_path: Directory containing skills
        """
        self.base_path = Path(base_path)
        self.skills: Dict[str, Skill] = {}
        self.scan_skills()

    def scan_skills(self):
        """Discover all skills in base_path"""
        logger.info(f"Scanning skills in {self.base_path}")

        if not self.base_path.exists():
            logger.warning(f"Skills directory not found: {self.base_path}")
            self.base_path.mkdir(parents=True, exist_ok=True)
            return

        # Look for skill directories
        for skill_dir in self.base_path.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                skill = self._load_skill(skill_md)
                if skill:
                    self.skills[skill.name] = skill
                    logger.debug(f"Loaded skill: {skill.name}")

    def _load_skill(self, skill_file: Path) -> Optional[Skill]:
        """Load a single skill from SKILL.md file"""
        try:
            content = skill_file.read_text()

            # Parse frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 2:
                    frontmatter = parts[1]
                    body = parts[2] if len(parts) > 2 else ""

                    # Parse YAML-like frontmatter
                    skill_data = self._parse_frontmatter(frontmatter)

                    # Set defaults for required fields
                    if 'name' not in skill_data:
                        skill_data['name'] = skill_file.parent.name
                    if 'description' not in skill_data:
                        skill_data['description'] = f"Skill: {skill_data['name']}"
                    if 'category' not in skill_data:
                        skill_data['category'] = 'general'
                    if 'triggers' not in skill_data:
                        skill_data['triggers'] = [skill_data['name']]

                    # Extract learned knowledge from body
                    learned = self._extract_learned_knowledge(body)
                    skill_data['learned_knowledge'] = learned

                    return Skill(**skill_data)

            return None

        except Exception as e:
            logger.error(f"Error loading skill from {skill_file}: {e}")
            return None

    def _parse_frontmatter(self, frontmatter: str) -> Dict[str, Any]:
        """Parse YAML-like frontmatter"""
        data = {}

        for line in frontmatter.strip().split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Handle different data types
                if value.lower() == 'true':
                    data[key] = True
                elif value.lower() == 'false':
                    data[key] = False
                elif value.startswith('[') and value.endswith(']'):
                    # Parse list
                    value = value[1:-1]
                    data[key] = [v.strip().strip('"\'') for v in value.split(',')]
                else:
                    data[key] = value.strip('"\'')

        return data

    def _extract_learned_knowledge(self, body: str) -> List[Dict]:
        """Extract learned knowledge items from markdown body"""
        learned = []

        # Look for learned knowledge sections
        if "## Learned Knowledge" in body:
            # Extract knowledge items
            pattern = r'###\s+(.+?)\s+\(confidence:\s+([\d.]+),\s+frequency:\s+(\d+)\)'
            matches = re.findall(pattern, body)

            for title, confidence, frequency in matches:
                learned.append({
                    'title': title.strip(),
                    'confidence': float(confidence),
                    'frequency': int(frequency),
                    'knowledge_type': 'pattern'
                })

        return learned

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get skill by name"""
        return self.skills.get(name)

    def get_skills_for_task(self, task: Task, top_n: int = 3) -> List[Skill]:
        """
        Find best skills for a task

        Args:
            task: Task to analyze
            top_n: Number of top skills to return

        Returns:
            List of skills sorted by relevance
        """
        scored_skills = [
            (skill, skill.matches_task(task.description))
            for skill in self.skills.values()
        ]

        # Filter and sort by confidence
        scored_skills = [
            (skill, score)
            for skill, score in scored_skills
            if score > 0.0
        ]
        scored_skills.sort(key=lambda x: x[1], reverse=True)

        return [skill for skill, _ in scored_skills[:top_n]]


class TaskAnalyzer:
    """Analyzes tasks and selects appropriate skills"""

    def __init__(self, skill_scanner: SkillScanner):
        """
        Initialize task analyzer

        Args:
            skill_scanner: Scanner for skill discovery
        """
        self.skill_scanner = skill_scanner

    def analyze_task(self, task: Task) -> Tuple[List[Skill], float]:
        """
        Analyze task and select skills

        Args:
            task: Task to analyze

        Returns:
            (selected_skills, overall_confidence)
        """
        # Get candidate skills
        candidate_skills = self.skill_scanner.get_skills_for_task(task, top_n=5)

        if not candidate_skills:
            logger.warning(f"No skills found for task: {task.description}")
            return [], 0.0

        # Calculate overall confidence
        confidences = [skill.matches_task(task.description) for skill in candidate_skills]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return candidate_skills, overall_confidence


class ExecutionEngine:
    """Main execution engine for SkillForge"""

    def __init__(self, config: ExecutionConfig):
        """
        Initialize execution engine

        Args:
            config: ExecutionConfig with settings
        """
        self.config = config
        self.skill_scanner = SkillScanner(config.SKILLS_BASE_PATH)
        self.task_analyzer = TaskAnalyzer(self.skill_scanner)
        self.execution_history: List[ExecutionResult] = []

        logger.info(f"ExecutionEngine initialized with {len(self.skill_scanner.skills)} skills")

    def create_task(self,
                   description: str,
                   user_files: Optional[List[str]] = None,
                   priority: TaskPriority = TaskPriority.NORMAL) -> Task:
        """
        Create a task from description

        Args:
            description: Task description
            user_files: Optional input files
            priority: Task priority

        Returns:
            Task object
        """
        task = Task(
            id="",  # Will be auto-generated
            description=description,
            priority=priority,
            user_files=user_files
        )

        # Analyze and select skills
        skills, confidence = self.task_analyzer.analyze_task(task)
        task.selected_skills = skills

        logger.info(f"Created task {task.id}: {description[:50]}... using {len(skills)} skills")

        return task

    def execute_task(self, task: Task) -> ExecutionResult:
        """
        Execute a task

        Args:
            task: Task to execute

        Returns:
            ExecutionResult with outcome
        """
        result = ExecutionResult(
            id=f"exec_{task.id}",
            task_id=task.id,
            status=ExecutionStatus.RUNNING,
            start_time=datetime.now(),
            selected_skills=task.selected_skills
        )

        try:
            logger.info(f"Executing task {task.id} with {len(task.selected_skills)} skills")

            if not task.selected_skills:
                result.status = ExecutionStatus.FAILED
                result.errors.append("No skills selected for task")
                result.end_time = datetime.now()
                return result

            # Simulate task execution with each skill
            for skill in task.selected_skills:
                logger.debug(f"Executing skill: {skill.name}")
                # In real implementation, would execute skill here
                # For now, simulate with random output
                import random
                if random.random() < 0.7:  # 70% success rate initially
                    result.outputs.append(Path(f"/output/{skill.name}_output.txt"))
                else:
                    result.errors.append(f"Error in skill {skill.name}")

            # Determine overall status
            if result.errors:
                result.status = ExecutionStatus.PARTIAL if result.outputs else ExecutionStatus.FAILED
            else:
                result.status = ExecutionStatus.COMPLETED

        except Exception as e:
            logger.error(f"Execution error: {e}")
            result.status = ExecutionStatus.FAILED
            result.errors.append(str(e))

        finally:
            result.end_time = datetime.now()
            self.execution_history.append(result)

        return result


# Convenience functions
def create_task_from_description(description: str) -> Task:
    """Quick task creation"""
    config = ExecutionConfig()
    engine = ExecutionEngine(config)
    return engine.create_task(description)


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    config = ExecutionConfig()
    engine = ExecutionEngine(config)

    # Create and execute sample task
    task = engine.create_task("Write a professional email about the project")
    result = engine.execute_task(task)

    print(f"Task: {task.description}")
    print(f"Status: {result.status.value}")
    print(f"Duration: {result.duration:.2f}s")
    print(f"Skills: {[s.name for s in result.selected_skills]}")
