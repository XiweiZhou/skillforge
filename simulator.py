#!/usr/bin/env python3
"""
SkillForge Simulator
Demonstrates cumulative skill improvement over time with realistic task execution
"""

import sys
import random
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass
import json

sys.path.insert(0, str(Path(__file__).parent))

from skillforge import SkillForge, ForgeResult
from execution_engine import Task, TaskPriority, ExecutionStatus, Skill
from learning_engine import ErrorEvent, SuccessPattern

import logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise during simulation


@dataclass
class SimulationConfig:
    """Configuration for simulation"""
    num_tasks: int = 100
    error_rate_initial: float = 0.25  # 25% initial error rate
    error_rate_decay: float = 0.8  # Errors reduce by 20% per 100 tasks
    skill_improvement_rate: float = 0.15  # 15% improvement per learning cycle
    verbose: bool = True
    save_results: bool = True


class TaskGenerator:
    """Generates realistic tasks for simulation"""
    
    def __init__(self):
        self.task_templates = {
            'email_writer': [
                "Write a professional email requesting a meeting",
                "Compose an email about project delays",
                "Draft a follow-up email for last week's meeting",
                "Create an email introducing a new team member",
                "Write an email declining a meeting request politely",
            ],
            'report_generator': [
                "Create a quarterly sales report from data.xlsx",
                "Generate a project status report",
                "Build a monthly analytics report",
                "Produce an executive summary report",
            ],
            'document_creator': [
                "Create a project proposal document",
                "Write a technical specification document",
                "Generate meeting minutes document",
                "Draft a policy document",
            ],
        }
        
        self.common_errors = {
            'email_writer': [
                ('SpamTriggerError', 'Email flagged as spam', 0.12),
                ('TimezoneError', 'Timezone not specified', 0.08),
                ('AttachmentError', 'Mentioned attachment but none attached', 0.05),
            ],
            'report_generator': [
                ('DataFormatError', 'Invalid data format', 0.15),
                ('FileNotFoundError', 'Input file not found', 0.10),
            ],
            'document_creator': [
                ('FormattingError', 'Inconsistent formatting', 0.12),
                ('TemplateError', 'Template not found', 0.08),
            ],
        }
    
    def generate_task(self, task_number: int, available_skills: List[str]) -> Tuple[str, str]:
        """
        Generate a realistic task
        
        Returns:
            (description, expected_skill)
        """
        # Weight towards available skills
        skill_weights = {
            'email_writer': 0.5,
            'report_generator': 0.3,
            'document_creator': 0.2,
        }
        
        skill = random.choices(
            list(skill_weights.keys()),
            weights=list(skill_weights.values())
        )[0]
        
        description = random.choice(self.task_templates.get(skill, ["Generic task"]))
        
        return description, skill
    
    def should_error(self, task_number: int, skill: str, error_rate: float) -> Tuple[bool, str, str]:
        """
        Determine if this task should error
        
        Returns:
            (should_error, error_type, error_message)
        """
        if random.random() > error_rate:
            return False, "", ""
        
        # Select a common error for this skill
        errors = self.common_errors.get(skill, [])
        if not errors:
            return False, "", ""
        
        error_type, error_message, _ = random.choice(errors)
        return True, error_type, error_message


class SimulationMetrics:
    """Tracks metrics during simulation"""
    
    def __init__(self):
        self.tasks_per_interval = []
        self.errors_per_interval = []
        self.success_rate_per_interval = []
        self.learning_cycles_per_interval = []
        self.knowledge_items_per_interval = []
        self.interval_size = 10
        
        self.current_interval_tasks = 0
        self.current_interval_errors = 0
        self.current_interval_successes = 0
        
    def record_task(self, success: bool):
        """Record a task result"""
        self.current_interval_tasks += 1
        if success:
            self.current_interval_successes += 1
        else:
            self.current_interval_errors += 1
        
        # Check if interval complete
        if self.current_interval_tasks >= self.interval_size:
            self._finalize_interval()
    
    def _finalize_interval(self):
        """Finalize current interval"""
        success_rate = self.current_interval_successes / self.current_interval_tasks
        
        self.tasks_per_interval.append(self.current_interval_tasks)
        self.errors_per_interval.append(self.current_interval_errors)
        self.success_rate_per_interval.append(success_rate)
        
        # Reset for next interval
        self.current_interval_tasks = 0
        self.current_interval_errors = 0
        self.current_interval_successes = 0
    
    def record_learning_cycle(self, knowledge_items: int):
        """Record a learning cycle"""
        # Add to current or create new
        if len(self.learning_cycles_per_interval) <= len(self.success_rate_per_interval):
            self.learning_cycles_per_interval.append(1)
            self.knowledge_items_per_interval.append(knowledge_items)
        else:
            self.learning_cycles_per_interval[-1] += 1
            self.knowledge_items_per_interval[-1] += knowledge_items
    
    def get_summary(self) -> Dict:
        """Get summary statistics"""
        if not self.success_rate_per_interval:
            return {}
        
        return {
            'initial_success_rate': self.success_rate_per_interval[0] if self.success_rate_per_interval else 0,
            'final_success_rate': self.success_rate_per_interval[-1] if self.success_rate_per_interval else 0,
            'improvement': (self.success_rate_per_interval[-1] - self.success_rate_per_interval[0]) if len(self.success_rate_per_interval) > 1 else 0,
            'total_errors': sum(self.errors_per_interval),
            'total_learning_cycles': sum(self.learning_cycles_per_interval),
            'total_knowledge_items': sum(self.knowledge_items_per_interval),
            'intervals': len(self.success_rate_per_interval),
        }


class SkillForgeSimulator:
    """
    Simulates realistic task execution to demonstrate learning
    """
    
    def __init__(self, config: SimulationConfig = None):
        self.config = config or SimulationConfig()
        self.task_generator = TaskGenerator()
        self.metrics = SimulationMetrics()
        
        # Initialize SkillForge
        self.forge = SkillForge(
            skills_dir=Path("/home/claude/skillforge/skills"),
            data_dir=Path("/home/claude/skillforge/data/simulation")
        )
        
        print("🔧 SkillForge Simulator initialized")
        print(f"   Tasks to simulate: {self.config.num_tasks}")
        print(f"   Initial error rate: {self.config.error_rate_initial:.1%}")
        print()
    
    def run(self) -> Dict:
        """
        Run the simulation
        
        Returns:
            Simulation results and metrics
        """
        print("=" * 70)
        print("STARTING SIMULATION")
        print("=" * 70)
        print()
        
        start_time = time.time()
        current_error_rate = self.config.error_rate_initial
        tasks_since_learning = 0
        
        for task_num in range(1, self.config.num_tasks + 1):
            # Generate task
            description, expected_skill = self.task_generator.generate_task(
                task_num,
                self.forge.list_skills()
            )
            
            # Simulate error
            should_error, error_type, error_msg = self.task_generator.should_error(
                task_num,
                expected_skill,
                current_error_rate
            )
            
            # Execute (simulate)
            success = not should_error
            
            if self.config.verbose and task_num % 10 == 0:
                print(f"Task {task_num}/{self.config.num_tasks} - "
                      f"Success rate: {self.metrics.current_interval_successes / max(1, self.metrics.current_interval_tasks):.1%}")
            
            # Record with learning engine
            self._simulate_task_execution(
                task_num=task_num,
                description=description,
                skill_name=expected_skill,
                success=success,
                error_type=error_type,
                error_msg=error_msg
            )
            
            # Record metrics
            self.metrics.record_task(success)
            tasks_since_learning += 1
            
            # Check if learning should trigger (every ~50 tasks or when error threshold met)
            if tasks_since_learning >= 50 or (not success and tasks_since_learning >= 10):
                knowledge_added = self._trigger_learning()
                if knowledge_added > 0:
                    self.metrics.record_learning_cycle(knowledge_added)
                    tasks_since_learning = 0
                    
                    # Improve error rate after learning
                    current_error_rate *= self.config.error_rate_decay
                    
                    if self.config.verbose:
                        print(f"   🎓 Learning cycle! Added {knowledge_added} knowledge items")
                        print(f"   📉 Error rate now: {current_error_rate:.1%}")
        
        # Final learning cycle
        knowledge_added = self._trigger_learning()
        if knowledge_added > 0:
            self.metrics.record_learning_cycle(knowledge_added)
        
        duration = time.time() - start_time
        
        print()
        print("=" * 70)
        print("SIMULATION COMPLETE")
        print("=" * 70)
        print(f"Duration: {duration:.2f}s")
        print()
        
        # Get results
        results = self._generate_results()
        
        # Print summary
        self._print_summary(results)
        
        # Save if requested
        if self.config.save_results:
            self._save_results(results)
        
        return results
    
    def _simulate_task_execution(self, task_num: int, description: str, skill_name: str,
                                 success: bool, error_type: str, error_msg: str):
        """Simulate a task execution and record with learning engine"""
        
        # Create a mock task
        task = Task(
            id=f"sim_task_{task_num}",
            description=description,
            priority=TaskPriority.NORMAL
        )
        
        # Mock skill
        task.selected_skills = [
            Skill(
                name=skill_name,
                path=Path(f"/home/claude/skillforge/skills/{skill_name}"),
                description=f"{skill_name} skill",
                file_types=[]
            )
        ]
        
        task.start_time = datetime.now()
        task.end_time = datetime.now() + timedelta(seconds=random.uniform(0.5, 2.0))
        task.execution_plan = ["step1", "step2", "step3"]
        
        if success:
            # Record success
            self.forge.learning_engine.record_task_success(task)
        else:
            # Record error
            error_class = type(error_type, (Exception,), {})
            error = error_class(error_msg)
            
            # Simulate recovery attempt (70% success after first occurrence)
            recovery_successful = random.random() > 0.3
            
            self.forge.learning_engine.record_task_error(
                task=task,
                error=error,
                step="EXECUTION",
                recovery_successful=recovery_successful,
                recovery_method=f"fix_{error_type.lower()}" if recovery_successful else None
            )
    
    def _trigger_learning(self) -> int:
        """Trigger a learning cycle and return knowledge items added"""
        initial_count = len(self.forge.learning_engine.repository.learned_knowledge)
        
        stats = self.forge.run_learning_cycle()
        
        final_count = len(self.forge.learning_engine.repository.learned_knowledge)
        
        return final_count - initial_count
    
    def _generate_results(self) -> Dict:
        """Generate simulation results"""
        summary = self.metrics.get_summary()
        forge_stats = self.forge.get_stats()
        
        return {
            'config': {
                'num_tasks': self.config.num_tasks,
                'initial_error_rate': self.config.error_rate_initial,
            },
            'metrics': summary,
            'forge_stats': forge_stats,
            'success_rate_over_time': self.metrics.success_rate_per_interval,
            'errors_over_time': self.metrics.errors_per_interval,
            'learning_cycles': self.metrics.learning_cycles_per_interval,
        }
    
    def _print_summary(self, results: Dict):
        """Print simulation summary"""
        metrics = results['metrics']
        
        print("📊 SIMULATION RESULTS")
        print()
        print(f"Initial Success Rate: {metrics['initial_success_rate']:.1%}")
        print(f"Final Success Rate: {metrics['final_success_rate']:.1%}")
        print(f"Improvement: {metrics['improvement']:.1%} ({metrics['improvement'] / metrics['initial_success_rate']:.1%} relative)")
        print()
        print(f"Total Errors: {metrics['total_errors']}")
        print(f"Learning Cycles: {metrics['total_learning_cycles']}")
        print(f"Knowledge Items Learned: {metrics['total_knowledge_items']}")
        print()
        
        # Show progression
        print("📈 SUCCESS RATE PROGRESSION")
        print()
        for i, rate in enumerate(results['success_rate_over_time']):
            tasks_range = f"{i*10+1}-{(i+1)*10}"
            bar = "█" * int(rate * 50)
            print(f"  Tasks {tasks_range:>7}: {bar} {rate:.1%}")
        print()
        
        # Learning impact
        print("🎓 LEARNING IMPACT")
        print()
        if metrics['total_learning_cycles'] > 0:
            print(f"  Average knowledge per cycle: {metrics['total_knowledge_items'] / metrics['total_learning_cycles']:.1f}")
            print(f"  Tasks between learning cycles: {self.config.num_tasks / metrics['total_learning_cycles']:.1f}")
        print()
        
        # SkillForge stats
        print("⚙️ SKILLFORGE STATS")
        print()
        print(f"  Skills available: {results['forge_stats']['skills']['available_skills']}")
        print(f"  Skills with learned knowledge: {results['forge_stats']['learning']['skills_with_knowledge']}")
        print(f"  Total knowledge items in DB: {results['forge_stats']['learning']['total_knowledge_items']}")
        print()
    
    def _save_results(self, results: Dict):
        """Save results to file"""
        output_dir = Path("/home/claude/skillforge/data/simulation/results")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"simulation_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"💾 Results saved to: {output_file}")
        print()


def main():
    """CLI interface for simulator"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SkillForge Simulator")
    parser.add_argument("--tasks", type=int, default=100, help="Number of tasks to simulate")
    parser.add_argument("--error-rate", type=float, default=0.25, help="Initial error rate (0.0-1.0)")
    parser.add_argument("--quiet", action="store_true", help="Reduce output")
    parser.add_argument("--no-save", action="store_true", help="Don't save results")
    
    args = parser.parse_args()
    
    config = SimulationConfig(
        num_tasks=args.tasks,
        error_rate_initial=args.error_rate,
        verbose=not args.quiet,
        save_results=not args.no_save
    )
    
    simulator = SkillForgeSimulator(config)
    results = simulator.run()
    
    return results


if __name__ == "__main__":
    main()
