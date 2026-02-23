# SkillForge

**Self-Improving Agents Through Closed-Loop Learning**

SkillForge demonstrates how autonomous agents can genuinely learn from experience through closed-loop feedback. Skills are defined declaratively via [AgentSkills.io](https://agentskills.io/specification)-compliant `SKILL.md` files -- no Python subclassing required. The engine handles execution, error detection, pattern learning, rule application, and rule lifecycle automatically.

## Core Concept

```
Task --> [Apply Rules] --> Execute --> Outcome --> Learn --> Update Rules
             ^                                                  |
             +-------------------- Knowledge Base <-------------+
```

**The key insight**: Knowledge must flow back into execution. Rules learned from past errors are evaluated against new tasks and actively prevent predicted failures -- and rules that stop working are automatically retired.

> **skill** — warm start: templates and structure ready from day one
> **forge** — calibration: watches every execution, builds rules, enforces them, and retires what doesn't work

## Quick Start

### Installation

```bash
git clone <repository-url>
cd skillforge
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-cov  # for development
```

### Run the Animated Demo

```bash
python3 scenarios/demo.py            # normal speed
python3 scenarios/demo.py --speed 0  # instant (CI / quick review)
python3 scenarios/demo.py --speed 2  # slow (presentations)
python3 scenarios/demo.py --seed 7   # different random sequence
```

The demo runs three acts in your terminal:
- **Act I** — Tasks execute with zero rules. Same errors repeat. Auto-learn fires mid-stream.
- **Act II** — Rules active. Forge enforces what it learned.
- **Act III** — A poorly-calibrated rule degrades ACTIVE → PROBATION → DORMANT, then gets resurrected when the same errors resurface.

### Run Tests

```bash
pytest tests/ -v
```

171 tests across 8 test files covering skill loading, knowledge rules, declarative execution, learning, LLM integration, multi-step execution, integration, and spec compliance.

## How Learning Works

### 1. Automatic Trigger

SkillForge monitors errors per skill and auto-triggers a learning cycle when enough uncovered signal accumulates -- no manual call needed:

```python
forge = SkillForge()

# Just execute tasks. Learning triggers automatically when:
# - 2+ distinct error types appear that no existing rule covers, OR
# - 20+ raw errors accumulate since the last cycle
result = forge.execute("Write email about the 3 PM meeting")
# TimezoneError logged → uncovered signal accumulates
# ...after enough failures, forge.run_learning_cycle() fires automatically
```

### 2. Pattern Detection

```python
# Can also trigger manually
metrics = forge.run_learning_cycle(min_frequency=3, min_confidence=0.3)

# Generated rule:
# IF task.description matches '\d{1,2}\s*(am|pm)'
# AND context.has_timezone == False
# THEN add_field(context.timezone, 'UTC')
#      flag(_flags, 'timezone_added')
```

### 3. Rule Application

```python
# Rules apply before execution (PREVENTION), after (VALIDATION),
# or on mid-execution failure (RECOVERY)
result = forge.execute("Send email about 2 PM meeting")
print(result.rules_applied)   # ['rule_timezoneerror_1']
```

### 4. Adaptive Confidence Updates

Rule confidence uses an adaptive exponential moving average. The prior dominates early (when few observations exist), observations dominate later:

```
prior_weight = 2.0 / (applications + 2)
confidence   = prior_weight × prior + (1 − prior_weight) × effectiveness
```

This allows rules to recover from initial bad luck and converge correctly without being locked in by early results.

### 5. Rule Lifecycle

Rules that underperform are demoted, not deleted. The knowledge is preserved for resurrection:

```
ACTIVE  →  effectiveness < threshold, n≥5   →  PROBATION
PROBATION  →  effectiveness ≥ threshold×1.1  →  ACTIVE      (hysteresis)
PROBATION  →  n≥15 AND eff < threshold×0.7  →  DORMANT
DORMANT  →  same error type resurfaces        →  ACTIVE      (resurrection)
```

Thresholds differ by rule type — PREVENTION rules are held to a higher standard (0.45) than RECOVERY rules (0.25), which face harder attribution problems.

Dormant rules fire the resurrection path in `add_rule()` the next time the learning cycle regenerates a rule for the same error type. The resurrected rule starts with partial confidence (`min(new_conf × 0.6, 0.5)`), not a full reset, so the degradation history informs the restart.

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

### Execution Tiers (priority order)

1. **`scripts/handler.py`** — full control via custom Python (highest priority)
2. **LLM-powered** — when an `llm_provider` is passed to `SkillForge()`, uses multi-step tool-calling loop
3. **Template-based** — intent matching against `assets/templates.yaml` (fallback)

### Optional: Templates

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
- `DeclarativeSkill`: Three-tier execution (handler → LLM → template), multi-step loop bounded by `max_steps`
- `SkillLoader`: Scans `skills/` directory, parses frontmatter, creates skill instances
- `SkillRegistry`: Trigger-based task matching with scoring (match count + earliest position)
- `StepRecord`: Per-step tracking of tool calls, tool results, errors, and recovery applied

**`knowledge.py`** -- Actionable Knowledge System
- `RuleStatus`: `ACTIVE` / `PROBATION` / `DORMANT` lifecycle states
- Rules with `Condition → Action` structure; conditions: `contains`, `matches`, `equals`, `gt`, `lt`
- `effective_confidence`: confidence × staleness decay (10% per 30 days idle, floor 50%)
- `PATTERN_LIBRARY`: Backbone intelligence shared across all skills — `TimezoneError`, `SpamTriggerError`, `AttachmentError`, `ConflictError`, `PreferenceError`, `PoorQueryError`, `LowCredibilityError`
- Adaptive EMA confidence updates in `record_outcome()`; lifecycle transitions in `_check_lifecycle()`
- `add_rule()` detects dormant resurrection and probation boost via semantic match (same `source_error_type` + `rule_type`)

**`learning.py`** -- Pattern Detection and Learning Engine
- `PatternDetector`: Groups errors by type, filters by `min_frequency` and `min_confidence = frequency / total_errors`
- `LearningEngine.run_learning_cycle()`: Two passes — PREVENTION rules from error repo, RECOVERY rules from step error repo
- Dormant-aware `already_has_rule` check: dormant rules are allowed to be re-derived and resurrected

**`skillforge.py`** -- Unified Interface
- `_maybe_auto_learn()`: Per-skill uncovered-error tracking, auto-triggers learning cycle
- Dynamic error classification derived from `PATTERN_LIBRARY` (keyword → error type)
- LLM-based error classification when a provider is available
- `reset()`: Clears stats and learning data; for clean KB state pass `data_dir=tempfile.mkdtemp()` at construction

**`llm.py`** -- LLM Providers
- `LLMProvider` ABC with `ClaudeProvider`, `OpenAIProvider`, `DeepSeekProvider`, `MockProvider`
- `MockProvider` supports `step_responses` list for deterministic multi-step test scenarios

## Project Structure

```
skillforge/
├── CLAUDE.md                       # Developer guide for Claude Code
├── pyproject.toml                  # Project config, pytest settings
├── requirements.txt                # Dependencies (anthropic, pyyaml, pydantic, etc.)
│
├── knowledge.py                    # Rules, conditions, actions, PATTERN_LIBRARY, RuleStatus
├── skills.py                       # DeclarativeSkill, SkillLoader, SkillRegistry, StepRecord
├── learning.py                     # ErrorRecord, PatternDetector, LearningEngine
├── llm.py                          # LLM provider abstraction (Claude, OpenAI, DeepSeek, Mock)
├── tools.py                        # ToolDefinition, ToolExecutor, ToolRegistry
├── skillforge.py                   # SkillForge orchestrator
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
├── scenarios/
│   ├── demo.py                     # Animated terminal demo (3 acts, rule lifecycle)
│   └── scenario_email.py           # Ablation scenario with train/test split
│
├── tests/                          # 171 tests
│   ├── conftest.py                 # Shared fixtures
│   ├── test_skill_loader.py        # SkillLoader, SkillRegistry
│   ├── test_knowledge.py           # Condition, Action, Rule, KnowledgeBase, RuleStatus
│   ├── test_declarative_skill.py   # ExecutionContext, DeclarativeSkill
│   ├── test_learning.py            # ErrorRepository, PatternDetector, LearningEngine
│   ├── test_llm.py                 # MockProvider, ClaudeProvider, multi-step loop
│   ├── test_tools.py               # ToolDefinition, ToolExecutor, ToolRegistry
│   ├── test_integration.py         # Full loop: execute → learn → improve
│   └── test_spec_compliance.py     # SKILL.md format validation (all 4 skills)
│
├── .github/workflows/ci.yml        # CI: test (Python 3.10-3.12) + spec validation
│
├── services/                       # External service integrations
│   ├── service_base.py
│   ├── mock_calendar_mcp.py
│   └── web_search_api.py
└── data/learning/                  # Runtime data (errors, rules, results)
```

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

### With LLM Provider

```python
from skillforge import SkillForge
from llm import ClaudeProvider

forge = SkillForge(llm_provider=ClaudeProvider())

# Skills now use the three-tier execution:
# 1. Custom handler (if present)
# 2. LLM multi-step tool loop
# 3. Template fallback
result = forge.execute("Write an email about the meeting at 3 PM")
```

### Learning Cycle (manual)

```python
# Auto-learning fires automatically, but you can also trigger manually
metrics = forge.run_learning_cycle(min_frequency=3, min_confidence=0.3)
print(f"Patterns detected: {metrics.patterns_detected}")
print(f"Rules generated: {metrics.rules_generated}")
```

### Statistics

```python
stats = forge.get_statistics()
print(f"Success rate: {stats['execution']['success_rate']:.1%}")
print(f"Total rules: {stats['learning']['total_rules']}")

# Rule lifecycle breakdown
kb_stats = forge.knowledge_base.get_statistics()
print(kb_stats['rules_by_status'])   # {'active': N, 'probation': N, 'dormant': N}
```

### Rule Inspection

```python
for rule in forge.knowledge_base.get_rules("email_writer"):
    print(f"{rule.name}: {rule.status.value}  "
          f"eff={rule.effectiveness:.2f}  conf={rule.effective_confidence:.2f}")
```

## Validation

SkillForge uses ablation testing to prove learning effectiveness (see `scenarios/scenario_email.py`):

- **Constant error rate**: No predetermined decay — improvement comes only from rules preventing errors
- **Train/test split**: Rules learned on training tasks, evaluated on held-out tasks
- **Ablation control**: Direct comparison with vs without learning applied

## CI/CD

GitHub Actions runs on every push and PR to `main`:

- **test**: Runs full test suite on Python 3.10, 3.11, 3.12
- **spec-validation**: Validates all `SKILL.md` files against spec requirements

## Limitations and Future Work

**Current limitations**:
- Pattern confidence is `frequency / total_errors` — minority error types can fall below threshold when dominated by a high-frequency type
- Attribution problem: all rules in `applied_rules` are credited/blamed equally; true causal attribution requires controlled experiments
- `PATTERN_LIBRARY` must be extended manually to support new error types

**Future directions**:
- Causal inference for pattern attribution
- Meta-learning across scenarios
- Multi-agent collaborative learning
- Real-world API integration

## Further Reading

- Blog post: [From Prompt Tweaks to Learning Machines: The Agent Skill Primitive](https://medium.com/@xiweizhou/from-prompt-tweaks-to-learning-machines-the-agent-skill-primitive-93c8fa9dec8c?sk=ac888430da699bce7b635456ae2b1166)
- Technical appendix: `docs/TECHNICAL_APPENDIX_EMAIL_SCENARIO_WALKTHROUGH.md`

## Built With

This repo was designed and architected by [Xiwei](https://github.com/xiweizhou), built using Claude Code as the primary development tool. The learning loop design, rule lifecycle model, ablation validation approach, and skill architecture are the result of iterative direction and review — Claude wrote implementation code from specifications and feedback.

## License

See LICENSE file for details.

---

**SkillForge** -- Agents that genuinely learn from experience through closed-loop feedback.
