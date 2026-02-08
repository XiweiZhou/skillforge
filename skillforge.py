#!/usr/bin/env python3
"""
SkillForge - Unified Interface
The main entry point that combines execution and learning engines
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution_engine import ExecutionEngine, Task, TaskPriority, ExecutionStatus, ExecutionConfig
from learning_engine import LearningEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SkillForge")


@dataclass
class ForgeResult:
    """Result of a SkillForge execution"""
    task_id: str
    success: bool
    outputs: List[Path]
    errors: List[str]
    duration: float
    skills_used: List[str]
    learned_something: bool = False
    
    def __str__(self):
        status = "✓ SUCCESS" if self.success else "✗ FAILED"
        return f"{status} ({self.duration:.2f}s) - {len(self.outputs)} outputs, {len(self.errors)} errors"


class SkillForge:
    """
    Unified interface for self-improving task execution
    
    Usage:
        forge = SkillForge()
        result = forge.execute("Create a PowerPoint about AI")
        print(result)
    
    Features:
        - Automatic skill selection
        - Intelligent execution planning
        - Error recovery with learning
        - Cumulative improvement over time
    """
    
    def __init__(self, 
                 skills_dir: Optional[Path] = None,
                 data_dir: Optional[Path] = None,
                 config: Optional[ExecutionConfig] = None):
        """
        Initialize SkillForge
        
        Args:
            skills_dir: Directory containing skills (default: /mnt/skills)
            data_dir: Directory for learning data (default: ./data/learning)
            config: Custom execution configuration
        """
        self.config = config or ExecutionConfig()
        
        # Set up directories
        if skills_dir:
            self.config.SKILLS_BASE_PATH = skills_dir
        
        self.data_dir = data_dir or Path("./data/learning")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize engines
        logger.info("Initializing SkillForge...")
        self.execution_engine = ExecutionEngine(self.config)
        self.learning_engine = LearningEngine(
            skills_dir=self.config.SKILLS_BASE_PATH,
            data_dir=self.data_dir
        )
        
        # Statistics
        self.tasks_executed = 0
        self.tasks_succeeded = 0
        self.tasks_failed = 0
        self.learning_cycles_triggered = 0
        
        logger.info("SkillForge ready!")
    
    def execute(self, 
                description: str,
                files: Optional[List[str]] = None,
                priority: str = "normal") -> ForgeResult:
        """
        Execute a task with automatic learning
        
        Args:
            description: Natural language task description
            files: Optional list of input files
            priority: Task priority (critical/high/normal/low)
        
        Returns:
            ForgeResult with execution details
        
        Example:
            result = forge.execute(
                "Create a report from sales_data.xlsx",
                files=["sales_data.xlsx"],
                priority="high"
            )
        """
        logger.info(f"Executing task: {description}")
        
        # Convert priority
        priority_map = {
            'critical': TaskPriority.CRITICAL,
            'high': TaskPriority.HIGH,
            'normal': TaskPriority.NORMAL,
            'low': TaskPriority.LOW,
        }
        task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
        
        # Create task
        task = self.execution_engine.create_task(
            description=description,
            user_files=files,
            priority=task_priority
        )
        
        # Execute with error tracking
        learned_something = False
        try:
            result = self.execution_engine.execute_task(task)
            
            # Record success
            if result.status == ExecutionStatus.COMPLETED:
                self.learning_engine.record_task_success(result)
                self.tasks_succeeded += 1
                logger.info(f"Task completed successfully")
            else:
                self.tasks_failed += 1
                logger.warning(f"Task failed: {result.status.value}")
            
        except Exception as e:
            logger.error(f"Task execution error: {e}")
            self.tasks_failed += 1
            
            # Record error and attempt learning
            if task.selected_skills:
                self.learning_engine.record_task_error(
                    task=task,
                    error=e,
                    step="EXECUTION",
                    recovery_successful=False,
                    recovery_method=None
                )
            
            # Re-raise for now (could handle differently)
            raise
        
        finally:
            self.tasks_executed += 1
        
        # Check if learning was triggered
        initial_knowledge_count = self._get_total_knowledge_items()
        
        # Manually trigger learning check if needed
        # (The learning engine auto-triggers at threshold, but we can force it)
        
        final_knowledge_count = self._get_total_knowledge_items()
        if final_knowledge_count > initial_knowledge_count:
            learned_something = True
            self.learning_cycles_triggered += 1
            logger.info(f"🎓 Learning triggered! Added {final_knowledge_count - initial_knowledge_count} knowledge items")
        
        # Create result
        duration = 0.0
        if result.end_time and result.start_time:
            duration = (result.end_time - result.start_time).total_seconds()
        
        forge_result = ForgeResult(
            task_id=result.id,
            success=result.status == ExecutionStatus.COMPLETED,
            outputs=result.outputs,
            errors=result.errors,
            duration=duration,
            skills_used=[s.name for s in result.selected_skills],
            learned_something=learned_something
        )
        
        return forge_result
    
    def run_learning_cycle(self) -> Dict[str, int]:
        """
        Manually trigger a learning cycle
        Useful for batch processing or scheduled learning
        
        Returns:
            Statistics about what was learned
        """
        logger.info("Running manual learning cycle...")
        stats = self.learning_engine.run_learning_cycle()
        if stats['skills_updated'] > 0:
            self.learning_cycles_triggered += 1
        return stats
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about SkillForge usage and learning
        
        Returns:
            Dictionary with usage and learning stats
        """
        learning_stats = self.learning_engine.get_learning_stats()
        
        return {
            'execution': {
                'tasks_executed': self.tasks_executed,
                'tasks_succeeded': self.tasks_succeeded,
                'tasks_failed': self.tasks_failed,
                'success_rate': self.tasks_succeeded / self.tasks_executed if self.tasks_executed > 0 else 0,
            },
            'learning': {
                'total_errors_recorded': learning_stats['total_errors'],
                'total_successes_recorded': learning_stats['total_successes'],
                'recovery_rate': learning_stats['recovery_rate'],
                'skills_with_knowledge': learning_stats['skills_with_learned_knowledge'],
                'total_knowledge_items': learning_stats['total_knowledge_items'],
                'learning_cycles_triggered': self.learning_cycles_triggered,
            },
            'skills': {
                'available_skills': len(self.execution_engine.skill_scanner.skills),
            }
        }
    
    def print_stats(self):
        """Print a formatted statistics report"""
        stats = self.get_stats()
        
        print("\n" + "=" * 70)
        print("SKILLFORGE STATISTICS")
        print("=" * 70)
        
        print("\nExecution:")
        print(f"  Tasks executed: {stats['execution']['tasks_executed']}")
        print(f"  Success rate: {stats['execution']['success_rate']:.1%}")
        print(f"  Succeeded: {stats['execution']['tasks_succeeded']}")
        print(f"  Failed: {stats['execution']['tasks_failed']}")
        
        print("\nLearning:")
        print(f"  Errors recorded: {stats['learning']['total_errors_recorded']}")
        print(f"  Successes recorded: {stats['learning']['total_successes_recorded']}")
        print(f"  Recovery rate: {stats['learning']['recovery_rate']:.1%}")
        print(f"  Learning cycles: {stats['learning']['learning_cycles_triggered']}")
        print(f"  Skills learned: {stats['learning']['skills_with_knowledge']}")
        print(f"  Knowledge items: {stats['learning']['total_knowledge_items']}")
        
        print("\nSkills:")
        print(f"  Available skills: {stats['skills']['available_skills']}")
        
        print("=" * 70 + "\n")
    
    def get_skill_info(self, skill_name: str) -> Optional[Dict]:
        """
        Get information about a specific skill
        
        Args:
            skill_name: Name of the skill
        
        Returns:
            Dictionary with skill information or None if not found
        """
        skill = self.execution_engine.skill_scanner.skills.get(skill_name)
        if not skill:
            return None
        
        learned = self.learning_engine.repository.get_learned_knowledge(skill_name)
        
        return {
            'name': skill.name,
            'description': skill.description,
            'category': skill.category,
            'file_types': skill.file_types,
            'triggers': skill.triggers,
            'learned_knowledge_items': len(learned),
            'learned_knowledge': [
                {
                    'type': k.knowledge_type,
                    'title': k.title,
                    'confidence': k.confidence,
                    'frequency': k.frequency,
                }
                for k in learned
            ]
        }
    
    def list_skills(self) -> List[str]:
        """Get list of all available skills"""
        return sorted(self.execution_engine.skill_scanner.skills.keys())
    
    def _get_total_knowledge_items(self) -> int:
        """Helper to count total learned knowledge items"""
        return sum(
            len(items) 
            for items in self.learning_engine.repository.learned_knowledge.values()
        )


# Convenience functions for quick usage
def execute(description: str, files: Optional[List[str]] = None) -> ForgeResult:
    """
    Quick execution without creating SkillForge instance
    
    Example:
        from skillforge import execute
        result = execute("Create a PowerPoint about AI")
    """
    forge = SkillForge()
    return forge.execute(description, files)


def main():
    """CLI interface for SkillForge"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SkillForge - Self-Improving Execution Engine")
    parser.add_argument("description", help="Task description")
    parser.add_argument("--files", nargs="*", help="Input files")
    parser.add_argument("--priority", choices=['critical', 'high', 'normal', 'low'], 
                       default='normal', help="Task priority")
    parser.add_argument("--stats", action="store_true", help="Show statistics after execution")
    parser.add_argument("--learn", action="store_true", help="Trigger learning cycle")
    
    args = parser.parse_args()
    
    forge = SkillForge()
    
    if args.learn:
        print("Running learning cycle...")
        stats = forge.run_learning_cycle()
        print(f"Learned: {stats}")
        return
    
    # Execute task
    result = forge.execute(args.description, args.files, args.priority)
    
    print(f"\nResult: {result}")
    
    if result.outputs:
        print(f"\nOutputs:")
        for output in result.outputs:
            print(f"  - {output}")
    
    if args.stats:
        forge.print_stats()


if __name__ == "__main__":
    main()
