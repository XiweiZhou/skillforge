# SkillForge

**Self-Improving Agents Through Closed-Loop Learning**

SkillForge is a research platform for building autonomous agents that **genuinely learn from experience**. The v2 architecture implements true closed-loop learning where knowledge is not just stored, but actively applied during execution to prevent errors.

## 🎯 Key Features (v2 Architecture)

- **Closed-Loop Learning**: Knowledge → Execution → Outcome → Learning → Knowledge
- **Actionable Rules**: Condition-based rules that actually prevent errors
- **Proper Validation**: Ablation testing comparing with/without learning
- **Constant Error Rates**: No predetermined decay - improvement comes from learning
- **Rule Effectiveness Tracking**: Confidence updates based on outcomes

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd skillforge

# Install dependencies
pip install -r requirements.txt
```

### Running the v2 Demo (Recommended)

```bash
# Run v2 demo with proper validation
python3 demo_v2.py --verbose

# Shows:
# - Training phase (collect errors at constant rate)
# - Learning phase (detect patterns, generate rules)
# - Evaluation phase (compare WITH vs WITHOUT learning)
```

### Running v1 Scenarios (Legacy)

```bash
# Run all 3 v1 scenarios (225 total tasks)
python3 demo_all.py --verbose

# Or run individual scenarios
python3 scenarios/scenario_1_email.py      # Email Assistant (100 tasks)
python3 scenarios/scenario_2_calendar.py   # Calendar Coordinator (50 tasks)
python3 scenarios/scenario_3_research.py   # Research Assistant (75 tasks)
```

## 🔄 v1 vs v2 Architecture

### v1 (Broken Loop)
```
Task → Execute (random) → Error → Learn Pattern → Update File → [DEAD END]
```
Knowledge was stored but never applied. "Improvement" came from predetermined error decay.

### v2 (Closed Loop)
```
Task → [Apply Rules] → Execute → Outcome → Learn → Update Rules
         ↑                                              ↓
         └──────────────── KnowledgeBase ←──────────────┘
```
Rules are applied during execution. Improvement comes from errors actually being prevented.

## 📊 Demonstration Scenarios

### Scenario 1: Email Assistant (Pure Skill Learning)
**Focus**: Pattern recognition without external services

- **Tasks**: 100 email composition tasks
- **Initial Error Rate**: 25%
- **Learning**: Detects spam triggers, timezone issues, attachment patterns
- **Result**: 90%+ success rate with 3 learned knowledge items
- **Key Learning**: Timezone handling, spam avoidance patterns

### Scenario 2: Calendar Coordinator (MCP Integration)
**Focus**: Service integration and conflict resolution

- **Tasks**: 50 meeting scheduling tasks
- **Services**: Mock calendar MCP with availability checking
- **Learning**: Timezone conflicts, participant preferences, scheduling patterns
- **Result**: 64%+ success rate with conflict reduction
- **Key Learning**: Preference patterns, scheduling heuristics

### Scenario 3: Research Assistant (Web API Integration)
**Focus**: Real API integration and information synthesis

- **Tasks**: 75 research queries
- **Services**: Web search API with credibility assessment
- **Learning**: Query optimization, source credibility, summary quality
- **Result**: 74%+ success rate with query improvements
- **Key Learning**: Query patterns, source credibility assessment

## 📈 Learning Architecture

### Execution Engine
```
Task Description
    ↓
SkillScanner (discovers matching skills)
    ↓
TaskAnalyzer (ranks skills by relevance)
    ↓
ExecutionEngine (executes selected skills)
    ↓
ExecutionResult (outputs + errors)
```

### Learning Engine
```
Execution Errors
    ↓
ErrorRepository (JSONL storage)
    ↓
PatternAnalyzer (frequency/confidence calculation)
    ↓
KnowledgeExtractor (converts patterns → knowledge items)
    ↓
SkillUpdater (appends knowledge to SKILL.md)
    ↓
Skills evolve with learned knowledge
```

## 🧠 How Learning Works

1. **Error Recording**: Each task execution error is recorded with context
2. **Pattern Detection**: After 10-50 errors, analyzer detects recurring patterns
3. **Confidence Calculation**: Patterns with 60%+ confidence and 5+ occurrences qualify
4. **Knowledge Extraction**: Patterns converted to human-readable knowledge items
5. **Skill Updates**: Knowledge appended to skill SKILL.md files
6. **Knowledge Persistence**: Learned items loaded on skill initialization

### Example Learned Knowledge

```markdown
### Timezone (confidence: 0.87, frequency: 12)
Avoid timezone ambiguity - always specify timezone for time-sensitive content
Learned from: 12 timezone confusion errors
```

## 📁 Project Structure

```
skillforge/
├── execution_engine.py          # Task execution and skill discovery
├── learning_engine.py           # Pattern detection and skill updates
├── skillforge.py                # Unified interface
├── simulator.py                 # Simulation framework
│
├── skills/                      # Skill library
│   ├── email_writer/
│   │   └── SKILL.md            # Skill definition with learned knowledge
│   ├── calendar_manager/
│   ├── web_searcher/
│   └── content_summarizer/
│
├── services/                    # External service integrations
│   ├── service_base.py          # Abstract service interfaces
│   ├── mock_calendar_mcp.py     # Mock MCP calendar service
│   └── web_search_api.py        # Web search integration
│
├── scenarios/                   # Demonstration scenarios
│   ├── scenario_1_email.py
│   ├── scenario_2_calendar.py
│   └── scenario_3_research.py
│
├── data/                        # Runtime data
│   └── learning/
│       ├── errors.jsonl         # Recorded execution errors
│       ├── successes.jsonl      # Recorded successes
│       ├── learned_knowledge.json
│       └── results/
│
└── requirements.txt             # Dependencies
```

## 🔧 Core Components

### ExecutionEngine
Discovers skills and executes tasks
- `SkillScanner`: Loads skills from filesystem, parses SKILL.md files
- `TaskAnalyzer`: Matches tasks to skills using trigger word matching
- `ExecutionEngine`: Main orchestration with error handling

### LearningEngine
Detects patterns and updates skills
- `ErrorRepository`: Stores errors as JSON lines
- `PatternAnalyzer`: Detects recurring error patterns
- `SkillUpdater`: Modifies SKILL.md with learned knowledge
- `KnowledgeRepository`: Persists learned knowledge across sessions

### Skill Definition (SKILL.md)
```yaml
---
name: email_writer
category: communication
triggers: ["email", "write", "compose"]
version: 1.0
---

# Email Writer Skill
Description and capabilities...

## Learned Knowledge
<!-- Auto-updated by LearningEngine -->
```

## 📊 Results Summary

From running the complete demo (225 tasks):

- **Email Assistant**: 90.0% success rate, 3 knowledge items
- **Calendar Coordinator**: 64.0% success rate, 0-1 knowledge items
- **Research Assistant**: 74.7% success rate, 4 knowledge items
- **Overall**: 79.1% success rate, 7 knowledge items learned

## 🎓 Learning Metrics

- **Total Learning Cycles**: 15 across all scenarios
- **Average Cycle Frequency**: Every 15 tasks
- **Min Pattern Frequency**: 3 occurrences (configurable)
- **Min Confidence Threshold**: 50% (configurable)
- **Knowledge Persistence**: Stored in JSON and skill files

## 🔌 Service Integration

### Mock Services (Development)
- **MockCalendarMCP**: Simulates calendar service with availability checking
- **MockWebSearchAPI**: Simulates web search with credibility scoring

### Real Service Ready
- **Web Search**: Designed to integrate with real search APIs (Brave, DuckDuckGo)
- **MCP Calendar**: Architecture supports real MCP calendar servers

## 🛠️ Development

### Adding a New Skill

1. Create skill directory:
```bash
mkdir skills/my_skill
```

2. Create SKILL.md:
```yaml
---
name: my_skill
category: general
triggers: ["trigger_word"]
version: 1.0
---

# My Skill
Description...

## Learned Knowledge
<!-- Auto-updated by LearningEngine -->
```

3. Skills are automatically discovered and loaded

### Running Learning Cycles

```python
from skillforge import SkillForge

forge = SkillForge()
# Execute tasks...
stats = forge.run_learning_cycle(min_frequency=5, min_confidence=0.60)
print(f"Learned {stats['knowledge_items_added']} new items")
```

### Accessing Learned Knowledge

```python
forge = SkillForge()
skill_info = forge.get_skill_info("email_writer")
print(f"Knowledge items: {skill_info['learned_knowledge_items']}")
for item in skill_info['learned_knowledge']:
    print(f"  - {item['title']}: {item['confidence']:.0%}")
```

## 📝 Configuration

All scenarios use configurable thresholds:

```python
# Lower thresholds = more aggressive learning
learn_stats = forge.learning_engine.run_learning_cycle(
    min_frequency=3,        # Minimum pattern occurrences
    min_confidence=0.50     # Minimum confidence score
)
```

## 🧪 Testing

Run individual scenario tests:
```bash
python3 -m pytest tests/test_scenarios.py -v
```

## 📚 Documentation

- `SETUP_AND_USAGE.md` - Detailed setup instructions
- `CODEBASE_REVIEW.md` - Architecture deep dive
- `INDEX.md` - Complete API reference
- `scenario_*_results.json` - Raw scenario results

## 🎯 Next Steps & Extensions

Potential enhancements:
- **Real MCP Integration**: Connect to actual calendar services
- **Multi-Skill Chains**: Coordinate multiple skills for complex tasks
- **Cross-Scenario Learning**: Transfer knowledge between scenarios
- **Performance Metrics**: Add latency and efficiency tracking
- **User Feedback Integration**: Learn from explicit user ratings
- **Web UI**: Dashboard for monitoring learning progress
- **Distributed Learning**: Support for multi-agent learning

## 📄 License

See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Areas for enhancement:
- Additional scenarios demonstrating learning
- Real service integrations
- Improved pattern detection algorithms
- Performance optimizations
- Documentation improvements

---

**SkillForge**: Agents that learn, improve, and adapt through experience.
