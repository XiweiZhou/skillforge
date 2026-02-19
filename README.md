# SkillForge

**Self-Improving Agents Through Closed-Loop Learning**

SkillForge demonstrates how autonomous agents can genuinely learn from experience through closed-loop feedback. Skills are defined declaratively via [AgentSkills.io](https://agentskills.io/specification)-compliant `SKILL.md` files -- no Python subclassing required. The engine handles execution, error detection, pattern learning, and rule application automatically.

## Core Concept

```
Task --> [Apply Rules] --> Execute --> Outcome --> Learn --> Update Rules
             ^                                                  |
             +-------------------- Knowledge Base <-------------+
```

**The key insight**: Knowledge must flow back into execution. Rules learned from past errors are evaluated against new tasks and actively prevent predicted failures.

## Quick Start

### Installation

```bash
git clone <repository-url>
cd skillforge
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov  # for development
```

### Run the Demo

```bash
python3 demo.py
```

### Run Tests

```bash
pytest tests/ -v
```

171 tests across 6 test files covering skill loading, knowledge rules, declarative execution, learning, integration, and spec compliance.

## Creating a New Skill

Create a directory under `skills/` with a single `SKILL.md` file:

```
skills/
  my-new-skill/
    SKILL.md          # required -- defines the skill
    assets/            # optional -- templates, data files
      templates.yaml
    scripts/           # optional -- custom Python handler
      handler.py
```

### Minimal SKILL.md

```markdown
---
name: my-new-skill
description: What this skill does.
metadata:
  triggers:
    - keyword1
    - keyword2
  output_type: result_type
---

# My New Skill

Detailed description in markdown.
```

That's it. SkillForge auto-discovers the skill, matches tasks to it via triggers, and wires up the learning loop. No code changes needed.

### Optional: Templates

Add `assets/templates.yaml` for intent-based output generation:

```yaml
greeting:
  match: [hello, hi]
  subject: "Greeting"
  body: "Hello there!"

default:
  match: []
  subject: "General"
  body: "Default output"
```

### Optional: Custom Handler

Add `scripts/handler.py` for full control over execution:

```python
from skills import ExecutionResult, ExecutionStatus, SkillOutput

def execute(context, metadata):
    return ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        output=SkillOutput(content={"key": "value"}, output_type="custom"),
    )
```

## Architecture

### Declarative Skills (AgentSkills.io Spec)

Skills are defined via `SKILL.md` with YAML frontmatter following the [AgentSkills.io specification](https://agentskills.io/specification). SkillForge-specific extensions live under the `metadata` field:

| Field | Purpose |
|-------|---------|
| `name` | Hyphenated lowercase identifier (e.g. `email-writer`) |
| `description` | What the skill does |
| `license` | License type |
| `metadata.triggers` | Keywords for task-to-skill matching |
| `metadata.output_type` | Output category |
| `metadata.context_fields` | Typed execution context fields with defaults |

### Included Skills

| Skill | Triggers | Output Type |
|-------|----------|-------------|
| `email-writer` | email, write email, compose, draft email | email |
| `calendar-manager` | calendar, schedule, meeting, book, reserve | calendar_event |
| `web-searcher` | search, find, research, look up, query | search_results |
| `content-summarizer` | summarize, summary, abstract, condense, extract | summary |

### Core Components

**`skills.py`** -- Declarative Skill System
- `ExecutionContext`: Dynamic properties via `__getattr__`/`__setattr__`, backward-compatible with rule dicts
- `DeclarativeSkill`: Driven by SKILL.md metadata, optional templates and handlers
- `SkillLoader`: Scans `skills/` directory, parses frontmatter, creates skill instances
- `SkillRegistry`: Trigger-based task matching with scoring (match count + earliest position)

**`knowledge.py`** -- Actionable Knowledge System
- Rules with `Condition -> Action` structure
- Conditions: `contains`, `matches`, `equals`, `greater_than`, `less_than`
- Actions: `add_field`, `flag`, `reject`, `transform`, `append`
- `PATTERN_LIBRARY`: Backbone intelligence shared across all skills
- Bayesian confidence updates from outcomes

**`learning.py`** -- Pattern Detection
- Analyzes error contexts beyond frequency counting
- Generates rules from `PATTERN_LIBRARY` templates
- Tracks rule effectiveness with outcome feedback

**`skillforge.py`** -- Unified Interface
- Coordinates skill selection, execution, and learning
- Dynamic error classification derived from `PATTERN_LIBRARY`
- Records outcomes for closed-loop feedback

## How Learning Works

### 1. Error Collection (Training)

```python
from skillforge import SkillForge

forge = SkillForge()

# Execute tasks -- errors are recorded with full context
result = forge.execute("Write email about meeting at 3 PM")
# Error: TimezoneError -- no timezone specified
```

### 2. Pattern Detection (Learning)

```python
# After collecting enough errors, detect patterns
metrics = forge.run_learning_cycle(min_frequency=3, min_confidence=0.3)

# Generated rule:
# IF task.description matches '\d{1,2}\s*(am|pm)'
# AND context.has_timezone == False
# THEN add_field(context.timezone, 'UTC')
#      flag(_flags, 'timezone_added')
```

### 3. Rule Application (Execution)

```python
# New task -- rule matches and applies before execution
result = forge.execute("Send email about 2 PM meeting")

# Rule prevents TimezoneError:
# - Detects "2 PM" in task
# - Checks context.has_timezone == False
# - Adds timezone to context
# - Email generated with timezone included
```

### 4. Outcome Feedback (Update)

```python
# Rule success updates confidence
# Bayesian update: confidence = 0.7 * prior + 0.3 * success_rate
```

## Project Structure

```
skillforge/
├── pyproject.toml                  # Project config, pytest settings
├── requirements.txt                # Dependencies (pyyaml, pydantic, etc.)
│
├── knowledge.py                    # Rules, conditions, actions, PATTERN_LIBRARY
├── skills.py                       # DeclarativeSkill, SkillLoader, SkillRegistry
├── learning.py                     # ErrorRecord, PatternDetector, LearningEngine
├── skillforge.py                   # SkillForge orchestrator
├── demo.py                         # Demonstration script
│
├── skills/                         # Skill definitions (AgentSkills.io spec)
│   ├── email-writer/
│   │   ├── SKILL.md
│   │   └── assets/templates.yaml
│   ├── calendar-manager/
│   │   ├── SKILL.md
│   │   └── assets/templates.yaml
│   ├── web-searcher/
│   │   └── SKILL.md
│   └── content-summarizer/
│       └── SKILL.md
│
├── tests/                          # 116 tests
│   ├── conftest.py                 # Shared fixtures
│   ├── test_skill_loader.py        # SkillLoader, SkillRegistry
│   ├── test_knowledge.py           # Condition, Action, Rule, KnowledgeBase
│   ├── test_declarative_skill.py   # ExecutionContext, DeclarativeSkill
│   ├── test_learning.py            # ErrorRepository, PatternDetector
│   ├── test_integration.py         # Full loop: execute -> learn -> improve
│   └── test_spec_compliance.py     # SKILL.md format validation (all 4 skills)
│
├── .github/workflows/ci.yml        # CI: test (Python 3.10-3.12) + spec validation
│
├── scenarios/                       # Training scenarios
│   └── scenario_email.py
├── services/                        # External service integrations
│   ├── service_base.py
│   ├── mock_calendar_mcp.py
│   └── web_search_api.py
└── data/learning/                   # Runtime data (errors, rules, results)
```

## CI/CD

GitHub Actions runs on every push and PR to `main`:

- **test**: Runs full test suite on Python 3.10, 3.11, 3.12
- **spec-validation**: Validates all `SKILL.md` files against spec requirements

## Usage Examples

### Basic Execution

```python
from skillforge import SkillForge

forge = SkillForge()

result = forge.execute("Write a professional email about the project")
print(f"Skill: {result.skill_name}")
print(f"Success: {result.success}")
print(f"Rules applied: {result.rules_applied}")
print(f"Output: {result.output}")
```

### Learning Cycle

```python
for task in training_tasks:
    forge.execute(task)

metrics = forge.run_learning_cycle(min_frequency=3, min_confidence=0.3)
print(f"Patterns detected: {metrics.patterns_detected}")
print(f"Rules generated: {metrics.rules_generated}")
```

### Statistics

```python
stats = forge.get_statistics()
print(f"Success rate: {stats['execution']['success_rate']:.1%}")
print(f"Total rules: {stats['learning']['total_rules']}")
```

## Validation

SkillForge uses ablation testing to prove learning effectiveness:

- **Constant error rate**: No predetermined decay
- **Train/test split**: Rules learned on training data, evaluated on held-out data
- **Ablation control**: Direct comparison with vs without learning applied

## Limitations and Future Work

**Current Limitations**:
- Simple pattern detection (frequency-based)
- Limited to error types in PATTERN_LIBRARY
- No cross-skill knowledge transfer

**Future Directions**:
- Causal inference for patterns
- Meta-learning across scenarios
- Multi-agent collaborative learning
- Real-world API integration

## Further Reading

- Blog post: [From Prompt Tweaks to Learning Machines: The Agent Skill Primitive](https://medium.com/@xiweizhou/from-prompt-tweaks-to-learning-machines-the-agent-skill-primitive-93c8fa9dec8c?sk=ac888430da699bce7b635456ae2b1166)
- Technical appendix: `docs/TECHNICAL_APPENDIX_EMAIL_SCENARIO_WALKTHROUGH.md`

## Built With

This repo was designed and architected by [Xiwei](https://github.com/xiweizhou), built using Claude Code as the primary development tool. The learning loop design, ablation validation approach, and skill architecture are the result of iterative direction and review — Claude wrote implementation code from specifications and feedback.

## License

See LICENSE file for details.

---

**SkillForge** -- Agents that genuinely learn from experience through closed-loop feedback.
