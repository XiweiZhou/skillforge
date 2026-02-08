# SkillForge

**Self-Improving Agents Through Closed-Loop Learning**

SkillForge demonstrates how autonomous agents can genuinely learn from experience through closed-loop feedback. Unlike traditional systems where "learning" is simulated through predetermined patterns, SkillForge implements true learning where knowledge is actively applied during execution to prevent errors.

## 🎯 Core Concept

```
Task → [Apply Rules] → Execute → Outcome → Learn → Update Rules
         ↑                                              ↓
         └──────────────── Knowledge Base ←─────────────┘
```

**The key insight**: Knowledge must flow back into execution. Rules learned from past errors are evaluated against new tasks and actively prevent predicted failures.

## 🚀 Quick Start

### Installation

```bash
git clone <repository-url>
cd skillforge
pip install -r requirements.txt
```

### Run the Demo

```bash
python3 demo.py
```

This demonstrates:
1. **Training Phase**: Collect errors at constant rate
2. **Learning Phase**: Detect patterns and generate actionable rules
3. **Evaluation Phase**: Compare performance WITH vs WITHOUT learning

### Typical Results

```
Training (50 tasks):
  Errors collected: 14-16 errors

Learning:
  Patterns detected: 1-2
  Rules generated: 1-2

Baseline (no learning): 60-68% success
With Learning:          76-78% success

Improvement: +10-16 percentage points ✓
```

## 📐 Architecture

### Core Components

**`knowledge.py`** - Actionable Knowledge System
- Rules with `Condition → Action` structure
- Conditions: `contains`, `matches`, `equals`, `gt`, `lt`
- Actions: `add_field`, `flag`, `reject`, `transform`
- Bayesian confidence updates from outcomes

**`skills.py`** - Skill Execution
- `EmailWriterSkill`, `CalendarManagerSkill`, `WebSearcherSkill`
- Apply prevention rules before execution
- Generate actual outputs (not random)
- Validation rules check results

**`learning.py`** - Pattern Detection
- Analyzes error contexts beyond frequency counting
- Generates rules from patterns
- Validates with proper train/test splits
- Tracks rule effectiveness

**`skillforge.py`** - Unified Interface
- Coordinates execution and learning
- Records outcomes for feedback
- Provides statistics and validation

## 📊 How Learning Works

### 1. Error Collection (Training)
```python
forge = SkillForge()

# Execute tasks - errors are recorded with full context
result = forge.execute("Write email about meeting at 3 PM")
# Error: TimezoneError - no timezone specified
```

### 2. Pattern Detection (Learning)
```python
# After collecting enough errors, detect patterns
metrics = forge.run_learning_cycle(min_frequency=3, min_confidence=0.5)

# Generated rule:
# IF task.description matches '\d{1,2}\s*(am|pm)'
# AND context.has_timezone == False
# THEN add_field(context.timezone, 'UTC')
```

### 3. Rule Application (Execution)
```python
# New task - rule matches and applies
result = forge.execute("Send email about 2 PM meeting")

# Rule prevents TimezoneError:
# - Detects "2 PM" in task
# - Checks context.has_timezone == False
# - Adds timezone to context
# - Email generated with timezone included
# - No error occurs ✓
```

### 4. Outcome Feedback (Update)
```python
# Rule success updates confidence
# Bayesian update: confidence = 0.7 * prior + 0.3 * success_rate
```

## 🧪 Validation

SkillForge uses proper ablation testing:

```python
# Phase 1: Baseline (no learning)
baseline = run_evaluation(apply_rules=False)
# Success: 60-68%

# Phase 2: With learning
learned = run_evaluation(apply_rules=True)
# Success: 76-78%

# Measure actual improvement
improvement = learned - baseline  # +10-16 pp
```

Key validation features:
- **Constant error rate**: No predetermined decay
- **Train/test split**: Rules learned on training set, evaluated on test set
- **Statistical comparison**: Proper hypothesis testing
- **Ablation control**: Direct comparison with/without learning

## 📁 Project Structure

```
skillforge/
├── README.md                    # This file
├── LICENSE                      # License
├── requirements.txt             # Dependencies
│
├── knowledge.py                 # Actionable knowledge system
├── skills.py                    # Skill implementations
├── learning.py                  # Pattern detection & learning
├── skillforge.py                # Main interface
├── demo.py                      # Complete demonstration
│
├── skills/                      # Skill definitions
│   ├── email_writer/
│   ├── calendar_manager/
│   └── web_searcher/
│
├── scenarios/                   # Training scenarios
│   └── scenario_email.py
│
├── services/                    # External service integrations
│   ├── service_base.py
│   ├── mock_calendar_mcp.py
│   └── web_search_api.py
│
├── data/learning/               # Runtime data
│   ├── errors.jsonl
│   ├── rules.json
│   └── results/
│
└── docs/                        # Additional documentation
    ├── ARCHITECTURE.md
    └── QUICK_START.md
```

## 💻 Usage Examples

### Basic Execution

```python
from skillforge import SkillForge

forge = SkillForge()

# Execute a task
result = forge.execute("Write a professional email about the project")

print(f"Success: {result.success}")
print(f"Rules applied: {result.rules_applied}")
print(f"Output: {result.output}")
```

### Learning Cycle

```python
# Execute many tasks to collect errors
for task in training_tasks:
    forge.execute(task)

# Run learning cycle
metrics = forge.run_learning_cycle()

print(f"Patterns detected: {metrics.patterns_detected}")
print(f"Rules generated: {metrics.rules_generated}")
```

### Statistics

```python
stats = forge.get_statistics()

print(f"Success rate: {stats['execution']['success_rate']:.1%}")
print(f"Total rules: {stats['learning']['total_rules']}")
print(f"Rule success rate: {stats['learning']['rule_success_rate']:.1%}")
```

## 🔬 Research Insights

### What Makes This Real Learning?

1. **Closed Loop**: Knowledge influences future execution
2. **Constant Baseline**: Error rates don't decrease artificially
3. **Actionable Rules**: Conditions trigger preventive actions
4. **Outcome Feedback**: Success/failure updates confidence
5. **Proper Validation**: Ablation tests prove effectiveness

### Limitations & Future Work

**Current Limitations**:
- Simple pattern detection (frequency-based)
- Limited to pre-defined error types
- No cross-skill knowledge transfer
- Single-agent learning only

**Future Directions**:
- Causal inference for patterns
- Meta-learning across scenarios
- Multi-agent collaborative learning
- Real-world API integration
- Neural approaches to pattern detection

## 📚 Documentation

- **README.md** (this file): Overview and quick start
- **docs/ARCHITECTURE.md**: Technical deep dive
- **docs/QUICK_START.md**: Step-by-step tutorial
- Inline code documentation with docstrings

## 🤝 Contributing

This is a research project demonstrating self-improving agents. Contributions welcome for:
- Additional skill implementations
- New learning algorithms
- Improved pattern detection
- Real service integrations
- Performance optimizations

## 📄 License

See LICENSE file for details.

---

**SkillForge** - Agents that genuinely learn from experience through closed-loop feedback.
