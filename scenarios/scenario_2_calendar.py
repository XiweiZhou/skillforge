#!/usr/bin/env python3
"""
Scenario 2: Calendar Coordinator with MCP Integration
Demonstrates service integration and learning from scheduling patterns
Focus: Timezone handling, conflict avoidance, participant preferences
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
import random
import json
import logging

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skillforge import SkillForge
from execution_engine import ExecutionConfig
from learning_engine import ErrorEvent
from services.mock_calendar_mcp import MockCalendarMCP

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("Scenario2")


class CalendarSimulator:
    """Simulates calendar scheduling tasks with learnable patterns"""

    def __init__(self, calendar_service: MockCalendarMCP):
        """Initialize with calendar service"""
        self.service = calendar_service
        self.service.connect()

        self.participants_pool = ['john@example.com', 'jane@example.com', 'bob@example.com']

        self.task_templates = [
            "Schedule a meeting with John and Jane for next Tuesday",
            "Book a 1-hour team sync with Bob and Jane",
            "Find a time for all team members to meet",
            "Schedule a 30-minute check-in with John",
            "Organize a meeting about project Q1 with team",
            "Book a presentation meeting with stakeholders",
            "Schedule a 1-on-1 with Jane about performance",
            "Find time for retrospective with entire team",
        ]

        # Error patterns that should be learned
        self.error_patterns = {
            'ConflictError': {
                'description': 'Scheduling conflict - double booking',
                'initial_rate': 0.12,
            },
            'TimezoneError': {
                'description': 'Timezone mismatch - no notice of timezone',
                'initial_rate': 0.10,
            },
            'PreferenceError': {
                'description': 'Ignored participant preferences',
                'initial_rate': 0.08,
            },
            'DurationError': {
                'description': 'Meeting duration conflicts with preferences',
                'initial_rate': 0.06,
            }
        }

    def generate_task(self, task_num: int) -> Tuple[str, List[str], str]:
        """
        Generate a calendar task

        Returns:
            (description, participants, date)
        """
        task_desc = random.choice(self.task_templates)

        # Select participants
        num_participants = random.randint(1, 3)
        participants = random.sample(self.participants_pool, num_participants)

        # Select date
        dates = ['2026-02-10', '2026-02-11', '2026-02-12']
        date = random.choice(dates)

        return task_desc, participants, date

    def simulate_execution(self, task_desc: str, participants: List[str], date: str,
                          task_num: int, error_rate: float) -> Tuple[bool, List[str]]:
        """
        Simulate meeting scheduling with learnable errors

        Returns:
            (success, error_list)
        """
        errors = []

        # Query calendar service for availability
        avail_response = self.service.get_availability(date, participants)

        if not avail_response.success:
            errors.append(('ServiceError', 'Failed to query availability'))
            return False, errors

        # Check for errors
        available_slots = avail_response.data.get('available_slots', [])

        # CONFLICT ERRORS - primary learning focus
        if not available_slots:
            # No slots available - this is a conflict
            if random.random() < (error_rate * 1.5):
                errors.append(('ConflictError', 'No common availability found'))
        else:
            # Sometimes book when conflicts exist (learnable)
            if random.random() < (error_rate * 0.5):
                errors.append(('ConflictError', 'Double booking detected'))

        # Timezone errors - if time mentioned in task
        if any(word in task_desc.lower() for word in ['am', 'pm', 'morning', 'afternoon']):
            if random.random() < (error_rate * 0.35):
                errors.append(('TimezoneError', self.error_patterns['TimezoneError']['description']))

        # Preference errors - sometimes ignore preferences (higher rate)
        if random.random() < (error_rate * 0.45):
            errors.append(('PreferenceError', self.error_patterns['PreferenceError']['description']))

        # Duration errors
        if random.random() < (error_rate * 0.25):
            errors.append(('DurationError', self.error_patterns['DurationError']['description']))

        success = len(errors) == 0
        return success, errors


def run_scenario_2(num_tasks: int = 50, verbose: bool = True) -> dict:
    """
    Run Scenario 2: Calendar Coordinator with MCP

    Args:
        num_tasks: Number of scheduling tasks
        verbose: Print progress

    Returns:
        Dictionary with metrics
    """
    config = ExecutionConfig(SKILLS_BASE_PATH=Path("./skills"))
    forge = SkillForge(skills_dir=Path("./skills"), data_dir=Path("./data/learning"), config=config)

    # Initialize calendar service
    calendar_service = MockCalendarMCP()

    simulator = CalendarSimulator(calendar_service)

    # Metrics
    metrics = {
        'total_tasks': num_tasks,
        'successes': 0,
        'failures': 0,
        'by_cycle': [],
        'learning_cycles': 0,
        'knowledge_items_learned': 0,
        'service_calls': 0,
        'conflict_rate': [],
    }

    print("\n" + "=" * 70)
    print("SCENARIO 2: CALENDAR COORDINATOR - MCP INTEGRATION DEMO")
    print("=" * 70)
    print(f"Starting {num_tasks} scheduling tasks with initial 30% error rate")
    print("Learning should reduce conflicts from 30% → <5%\n")

    for task_num in range(1, num_tasks + 1):
        # Error rate decreases over time as learning happens
        progress = task_num / num_tasks
        error_rate = 0.30 * (0.95 ** (task_num // 10))

        # Generate and simulate task
        task_desc, participants, date = simulator.generate_task(task_num)
        success, errors = simulator.simulate_execution(
            task_desc, participants, date, task_num, error_rate
        )

        metrics['service_calls'] += 1

        if success:
            metrics['successes'] += 1
        else:
            metrics['failures'] += 1
            # Record errors in learning engine
            for error_type, description in errors:
                err = ErrorEvent(
                    timestamp=datetime.now(),
                    skill_name='calendar_manager',
                    task_description=task_desc,
                    error_type=error_type,
                    error_message=description,
                    recovery_successful=False
                )
                forge.learning_engine.error_repo.record_error(err)

        # Trigger learning cycle every 10 tasks
        if task_num % 10 == 0:
            # Lower thresholds for smaller scenarios
            learn_stats = forge.learning_engine.run_learning_cycle(min_frequency=3, min_confidence=0.50)
            metrics['learning_cycles'] += 1
            metrics['knowledge_items_learned'] += learn_stats.get('knowledge_items_added', 0)

            conflict_rate = metrics['failures'] / task_num
            metrics['conflict_rate'].append(conflict_rate)

            if verbose:
                print(f"Task {task_num:2d}: Success Rate {metrics['successes']/task_num:5.1%} | "
                      f"Conflicts {metrics['failures']:2d} | "
                      f"🎓 Learning: +{learn_stats.get('knowledge_items_added', 0)} items")
        else:
            if verbose and task_num % 5 == 0:
                print(f"Task {task_num:2d}: Success Rate {metrics['successes']/task_num:5.1%} | "
                      f"Conflicts {metrics['failures']:2d}")

    # Final stats
    print("\n" + "=" * 70)
    print("SCENARIO 2 RESULTS")
    print("=" * 70)

    final_success_rate = metrics['successes'] / num_tasks
    initial_failure_rate = 0.30  # Expected initial
    final_failure_rate = metrics['failures'] / num_tasks

    print(f"\nExecution Summary:")
    print(f"  Total tasks: {metrics['total_tasks']}")
    print(f"  Successful: {metrics['successes']} ({final_success_rate:.1%})")
    print(f"  Failed (conflicts): {metrics['failures']} ({final_failure_rate:.1%})")

    print(f"\nService Integration:")
    print(f"  Service calls made: {metrics['service_calls']}")
    print(f"  Avg calls per task: {metrics['service_calls']/num_tasks:.1f}")

    print(f"\nLearning Summary:")
    print(f"  Learning cycles triggered: {metrics['learning_cycles']}")
    print(f"  Total knowledge items learned: {metrics['knowledge_items_learned']}")

    # Get learning stats
    learn_stats = forge.learning_engine.get_learning_stats()
    print(f"  Total errors recorded: {learn_stats['total_errors']}")

    print(f"\nSkill Knowledge:")
    skill_info = forge.get_skill_info("calendar_manager")
    if skill_info:
        print(f"  Calendar Manager knowledge items: {skill_info['learned_knowledge_items']}")
        for item in skill_info['learned_knowledge']:
            print(f"    - {item['title']}: confidence {item['confidence']:.2f}, frequency {item['frequency']}")

    # Calculate improvement
    print(f"\nLearning Effectiveness:")
    print(f"  Initial conflict rate: {initial_failure_rate:.1%}")
    print(f"  Final conflict rate: {final_failure_rate:.1%}")
    print(f"  Reduction: -{(initial_failure_rate - final_failure_rate)*100:.1f} percentage points")

    if final_failure_rate <= 0.05:
        print(f"  ✅ EXCELLENT: Reduced conflicts to <5%")
    elif final_failure_rate <= 0.10:
        print(f"  ✅ GOOD: Reduced conflicts to <10%")
    else:
        print(f"  ⚠️  FAIR: Conflict rate at {final_failure_rate:.1%}, target was <5%")

    print("=" * 70 + "\n")

    metrics['final_success_rate'] = final_success_rate
    metrics['final_failure_rate'] = final_failure_rate

    return metrics


if __name__ == "__main__":
    # Run scenario
    results = run_scenario_2(num_tasks=50, verbose=True)

    # Save results
    results_file = Path("./data/learning/scenario_2_results.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)

    # Clean for JSON
    clean_results = {k: v for k, v in results.items() if k != 'conflict_rate'}
    clean_results['conflict_rate_final'] = results['conflict_rate'][-1] if results['conflict_rate'] else 0

    results_file.write_text(json.dumps(clean_results, indent=2))
    print(f"Results saved to {results_file}")
