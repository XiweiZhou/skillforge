# SkillForge Quick Start Guide

Get SkillForge up and running in **5 minutes**.

## Installation (2 minutes)

```bash
# Navigate to project directory
cd skillforge

# Install Python dependencies
pip install -r requirements.txt
```

**That's it!** No database setup, no configuration files needed.

## Running the Demo (3 minutes)

### Option 1: Run Complete Demonstration (Recommended)

```bash
# Run all 3 scenarios with verbose output
python3 demo_all.py --verbose

# Expected output: ~100 lines of progress
# Estimated time: 5-10 seconds
```

This runs:
- **Scenario 1**: 100 email tasks (2-3 seconds)
- **Scenario 2**: 50 calendar tasks (1-2 seconds)
- **Scenario 3**: 75 research tasks (2-3 seconds)

### Option 2: Run Individual Scenarios

```bash
# Email Assistant
python3 scenarios/scenario_1_email.py

# Calendar Coordinator
python3 scenarios/scenario_2_calendar.py

# Research Assistant
python3 scenarios/scenario_3_research.py
```

## Understanding the Output

### Progress Display

```
Task  10: Success Rate 90.0%
Task  20: Success Rate 90.0% | 🎓 Learning: +1 knowledge items
```

- **Task N**: Current task number
- **Success Rate**: Cumulative success percentage
- **🎓 Learning**: Knowledge items added in learning cycle

### Final Results

```
======================================================================
SCENARIO 1 RESULTS
======================================================================

Execution Summary:
  Total tasks: 100
  Successful: 90 (90.0%)
  Failed: 10 (10.0%)

Learning Summary:
  Learning cycles triggered: 5
  Total knowledge items learned: 3
  Total errors recorded: 12

Skill Knowledge:
  Email Writer knowledge items: 3
    - Timezone: confidence 0.71, frequency: 5
```

- **Success Rate**: % of tasks completed without errors
- **Learning Cycles**: How many times patterns were detected and learned
- **Knowledge Items**: New patterns the agent learned
- **Confidence**: How sure the system is about this pattern (0-1)
- **Frequency**: How many times this pattern was observed

## Checking Learned Knowledge

After running scenarios, view what was learned:

### View in JSON Format

```bash
cat data/learning/learned_knowledge.json
```

Output:
```json
{
  "email_writer": [
    {
      "title": "Timezone",
      "confidence": 0.71,
      "frequency": 5,
      "description": "Pattern detected: TimezoneError..."
    }
  ]
}
```

### View in Skill Files

```bash
cat skills/email_writer/SKILL.md
```

Output:
```markdown
## Learned Knowledge
<!-- This section auto-updated by LearningEngine -->
### Timezone (confidence: 0.71, frequency: 5)
Pattern detected: TimezoneError. Example: Timezone not specified...
```

## Directory Structure After Running

```
skillforge/
├── skills/
│   ├── email_writer/
│   │   └── SKILL.md (updated with learned knowledge)
│   ├── calendar_manager/
│   └── web_searcher/
│
└── data/
    └── learning/
        ├── errors.jsonl          (error log)
        ├── learned_knowledge.json (persisted knowledge)
        ├── scenario_1_results.json
        ├── scenario_2_results.json
        ├── scenario_3_results.json
        └── COMPREHENSIVE_RESULTS.json
```

## Using SkillForge in Your Code

### Basic Usage

```python
from skillforge import SkillForge

# Initialize
forge = SkillForge()

# Execute a task
result = forge.execute("Write a professional email about the project")

# Check result
print(f"Success: {result.success}")
print(f"Skills used: {result.skills_used}")
print(f"Duration: {result.duration}s")
```

### Running Learning Cycles

```python
from skillforge import SkillForge

forge = SkillForge()

# Execute tasks...
for i in range(50):
    task = f"Task {i}"
    forge.execute(task)

# Manually trigger learning
stats = forge.run_learning_cycle()
print(f"Learned {stats['knowledge_items_added']} new items")
```

### Checking Statistics

```python
forge = SkillForge()

# Get comprehensive stats
stats = forge.get_stats()
print(f"Success rate: {stats['execution']['success_rate']:.1%}")
print(f"Knowledge items: {stats['learning']['total_knowledge_items']}")

# Pretty print
forge.print_stats()
```

### Accessing Skill Information

```python
forge = SkillForge()

# Get skill details
skill_info = forge.get_skill_info("email_writer")
print(f"Skill: {skill_info['name']}")
print(f"Category: {skill_info['category']}")
print(f"Learned knowledge:")
for item in skill_info['learned_knowledge']:
    print(f"  - {item['title']}: {item['confidence']:.0%} confidence")

# List all skills
all_skills = forge.list_skills()
print(f"Available skills: {all_skills}")
```

## Key Concepts

### Skills
Self-contained modules for specific tasks. Each skill:
- Has triggers (keywords that activate it)
- Learns from errors
- Updates its knowledge file over time

Example skill file structure:
```yaml
---
name: email_writer
category: communication
triggers: ["email", "write", "compose"]
---
# Email Writer Skill
[description]

## Learned Knowledge
<!-- Auto-updated by LearningEngine -->
```

### Learning Cycles
Automatic process that:
1. Analyzes recorded errors
2. Detects recurring patterns
3. Generates knowledge items
4. Updates skill files

Triggered automatically or manually via `run_learning_cycle()`

### Error Patterns
Recurring issues the system learns from:
- SpamTriggerError
- TimezoneError
- ConflictError
- etc.

When patterns reach sufficient frequency (5+) and confidence (60%+), they become knowledge items.

## Configuration

### Adjust Learning Aggressiveness

```python
# More aggressive - learns from fewer errors
stats = forge.learning_engine.run_learning_cycle(
    min_frequency=3,        # Need 3+ occurrences
    min_confidence=0.45     # Need 45%+ confidence
)

# More conservative - requires more evidence
stats = forge.learning_engine.run_learning_cycle(
    min_frequency=10,       # Need 10+ occurrences
    min_confidence=0.75     # Need 75%+ confidence
)
```

### Adjust Execution Config

```python
from execution_engine import ExecutionConfig

config = ExecutionConfig(
    SKILLS_BASE_PATH="/custom/skills/path",
    TIMEOUT_SECONDS=600,
    MAX_RETRIES=3,
    LOG_LEVEL="DEBUG"
)

forge = SkillForge(config=config)
```

## Troubleshooting

### No Skills Found

```
ERROR: ExecutionEngine - Error loading skill from skills/email_writer/SKILL.md
```

**Solution**: Ensure skill directories exist and SKILL.md files are properly formatted:
```yaml
---
name: email_writer
category: communication
triggers: ["email"]
---
```

### No Learning Happening

**Check error count**:
```bash
wc -l data/learning/errors.jsonl
```

Need at least 3-5 errors to trigger learning.

**Check learning cycles**:
```python
stats = forge.learning_engine.run_learning_cycle()
print(stats)
```

Should show `'patterns_detected'` > 0 if errors exist.

### Out of Memory

Large simulations may need adjusted thresholds:
```bash
# Reduce tasks
python3 scenarios/scenario_1_email.py --tasks 50
```

## Next Steps

1. **Explore the Code**
   - Read `execution_engine.py` to understand task execution
   - Read `learning_engine.py` to understand learning
   - Check `scenarios/` for example implementations

2. **Add Your Own Skill**
   ```bash
   mkdir skills/my_skill
   # Create skills/my_skill/SKILL.md
   ```

3. **Read Full Documentation**
   - `README.md` - Project overview
   - `RESULTS.md` - Detailed results and findings
   - `CODEBASE_REVIEW.md` - Architecture deep dive
   - `INDEX.md` - API reference

4. **Experiment**
   - Modify scenario error rates
   - Adjust learning thresholds
   - Add new skills

## Support

For questions or issues:
1. Check `RESULTS.md` for detailed findings
2. Review `CODEBASE_REVIEW.md` for architecture
3. See example scenarios in `scenarios/` directory

---

**SkillForge Quick Start** - Ready to learn? Run `python3 demo_all.py` now!
