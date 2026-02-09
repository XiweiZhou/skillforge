#!/usr/bin/env python3
"""
SkillForge Complete Demonstration
Shows closed-loop learning with proper validation
"""

import sys
from pathlib import Path
import json
from datetime import datetime
import logging
import shutil

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.WARNING)

from scenarios.scenario_email import run_complete_scenario as run_email_scenario


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(title.center(70))
    print("=" * 70)


def print_section(title: str):
    """Print a section divider"""
    print(f"\n  {title}")
    print(f"  {'-' * len(title)}")


def clear_learning_data():
    """Clear all learning data for fresh start"""
    data_dir = Path("./data/learning")
    if data_dir.exists():
        for file in data_dir.glob("*"):
            if file.is_file():
                file.unlink()
    data_dir.mkdir(parents=True, exist_ok=True)


def run_demo(verbose: bool = True, seed: int | None = None) -> dict:
    """
    Run the complete SkillForge demonstration.

    This demo shows:
    1. Closed-loop learning: errors -> patterns -> rules -> prevention
    2. Ablation testing: with vs without learned knowledge
    3. Statistically valid improvement measurement
    """
    print_header("SKILLFORGE - CLOSED-LOOP LEARNING DEMO")

    print("""
  SkillForge agents learn from their mistakes and get better over time.
  This demonstration proves it with measurable results.

  HOW IT WORKS:
    1. Execute tasks at a constant error rate (no rigging)
    2. Detect error patterns automatically
    3. Generate actionable prevention rules
    4. Apply rules during execution to prevent errors
    5. Validate improvement with ablation testing

  THREE PHASES:
    Phase 1  TRAIN    Execute tasks, collect errors at constant rate
    Phase 2  LEARN    Detect patterns, generate prevention rules
    Phase 3  EVAL     Compare WITH vs WITHOUT learned rules
""")

    # Clear previous data
    clear_learning_data()

    all_results = {
        'timestamp': datetime.now().isoformat(),
        'scenarios': {},
    }

    # Run Email Assistant scenario
    print_header("SCENARIO: EMAIL ASSISTANT")
    email_results = run_email_scenario(num_training=50, num_eval=50, verbose=verbose, seed=seed)
    all_results['scenarios']['email_assistant'] = email_results

    # Summary
    print_header("RESULTS SUMMARY")

    for name, results in all_results['scenarios'].items():
        baseline = results['baseline']['success_rate']
        learned = results['with_learning']['success_rate']
        improvement = results['improvement']

        print_section(name.upper().replace('_', ' '))
        print(f"  Baseline (no learning):  {baseline:>6.1%}")
        print(f"  With learning:           {learned:>6.1%}")
        print(f"  Improvement:             {improvement*100:>+5.1f} pp")
        print()
        print(f"  Rules generated:  {results['learning']['rules_generated']}")
        print(f"  Rules applied:    {results['with_learning']['rules_applied_total']}")
        print(f"  Errors prevented: {results['with_learning']['errors_prevented']}")

    total_improvement = sum(
        r['improvement'] for r in all_results['scenarios'].values()
    )
    avg_improvement = total_improvement / len(all_results['scenarios'])

    print_header("CONCLUSION")

    if avg_improvement > 0.10:
        verdict = "HIGHLY EFFECTIVE"
    elif avg_improvement > 0.05:
        verdict = "EFFECTIVE"
    elif avg_improvement > 0:
        verdict = "PROMISING"
    else:
        verdict = "NEEDS IMPROVEMENT"

    print(f"""
  Learning is {verdict} ({avg_improvement*100:+.1f} pp average improvement)

  The closed loop in action:
    Knowledge --> Execution --> Outcome --> Learning --> Knowledge
       ^                                                   |
       +---------------------------------------------------+

  What happened:
    - PatternDetector found recurring error types
    - RuleGenerator created actionable rules (condition -> action)
    - KnowledgeBase applied rules during execution
    - Rules prevented errors that would otherwise have occurred
    - Rule outcomes fed back to update confidence scores
""")
    print("=" * 70 + "\n")

    # Save results
    results_file = Path("./data/learning/demo_results.json")
    results_file.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"Results saved to: {results_file}\n")

    return all_results


def show_architecture():
    """Show SkillForge architecture overview"""
    print_header("SKILLFORGE ARCHITECTURE")

    print("""
  EXECUTION PIPELINE
  ==================

    Task Description
         |
         v
    Skill Selection (from SKILL.md declarations)
         |
         v
    +----+----+----------+
    |         |          |
    v         v          v
  handler   LLM       template
  .py     powered     fallback
  (pri 1) (pri 2)    (pri 3)
    |         |          |
    +----+----+----------+
         |
         v
    ExecutionResult


  MULTI-STEP LLM EXECUTION (with knowledge-informed recovery)
  ============================================================

    for step in range(max_steps):
      |
      +-> LLM generates response (with accumulated tool results)
      |
      +-> No tool calls? -> Done (final output ready)
      |
      +-> Execute tool calls
      |     |
      |     +-> Success -> accumulate results, next step
      |     |
      |     +-> Failure -> classify error
      |                      |
      |                      +-> Look up RECOVERY rules
      |                      +-> Apply recovery to context
      |                      +-> Inject recovery info for LLM
      |                      +-> next step (LLM sees what happened)
      |
      +-> Record StepRecord (tool_calls, results, errors, recovery)


  CLOSED-LOOP LEARNING
  ====================

    Execution errors (task-level + step-level)
         |
         v
    PatternDetector (min_frequency, min_confidence)
         |
         v
    RuleGenerator
      +-> PREVENTION rules  (from task errors)
      +-> RECOVERY rules    (from step errors)
         |
         v
    KnowledgeBase
      +-> PREVENTION applied before execution
      +-> VALIDATION applied after execution
      +-> RECOVERY applied mid-execution on tool failure
         |
         v
    Outcome feedback updates rule confidence
         |
         +---------> next execution cycle
""")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="SkillForge Demonstration")
    parser.add_argument("--verbose", action="store_true", help="Show detailed progress")
    parser.add_argument("--architecture", action="store_true", help="Show architecture overview")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible results")

    args = parser.parse_args()

    if args.architecture:
        show_architecture()
        return

    verbose = not args.quiet

    # Run demonstration
    results = run_demo(verbose=verbose, seed=args.seed)

    print("SkillForge demonstration complete.")


if __name__ == "__main__":
    main()
