# SkillForge Setup & Usage Guide

## 🚀 Quick Start (5 Minutes)

### **Step 1: Set Up Environment**

```bash
# Navigate to skillforge directory
cd /home/claude/skillforge

# Install dependencies (minimal)
pip install pyyaml --break-system-packages

# Verify structure
ls -R
```

### **Step 2: Run Your First Simulation**

```bash
# Run a quick simulation (100 tasks)
python simulator.py --tasks 100

# Watch the magic happen:
# - Tasks execute
# - Errors occur
# - Patterns detected
# - Skills learn automatically
# - Success rate improves!
```

### **Step 3: See Cumulative Improvement**

```bash
# Run longer simulation
python simulator.py --tasks 500

# Compare results:
# - Initial success rate: ~75%
# - Final success rate: ~95%
# - 20+ percentage point improvement!
```

---

## 📊 What You'll See

### **Example Output:**

```
🔧 SkillForge Simulator initialized
   Tasks to simulate: 100
   Initial error rate: 25.0%

====================================================================================
STARTING SIMULATION
====================================================================================

Task 10/100 - Success rate: 70.0%
Task 20/100 - Success rate: 75.0%
   🎓 Learning cycle! Added 2 knowledge items
   📉 Error rate now: 20.0%
Task 30/100 - Success rate: 80.0%
Task 40/100 - Success rate: 83.0%
   🎓 Learning cycle! Added 1 knowledge items
   📉 Error rate now: 16.0%
...

====================================================================================
SIMULATION COMPLETE
====================================================================================

📊 SIMULATION RESULTS

Initial Success Rate: 70.0%
Final Success Rate: 93.5%
Improvement: +23.5% (33.6% relative)

Total Errors: 15
Learning Cycles: 3
Knowledge Items Learned: 5

📈 SUCCESS RATE PROGRESSION

  Tasks    1-10: ███████████████████████████████████ 70.0%
  Tasks  11-20: ████████████████████████████████████████ 80.0%
  Tasks  21-30: █████████████████████████████████████████████ 86.0%
  Tasks  31-40: ████████████████████████████████████████████████ 90.0%
  Tasks  41-50: ██████████████████████████████████████████████████ 92.0%
  Tasks  51-60: ███████████████████████████████████████████████████ 93.0%
  Tasks  61-70: ███████████████████████████████████████████████████ 93.5%
  Tasks  71-80: ███████████████████████████████████████████████████ 93.5%
  Tasks  81-90: ███████████████████████████████████████████████████ 93.5%
  Tasks 91-100: ███████████████████████████████████████████████████ 93.5%
```

---

## 🎯 Understanding The Improvement

### **What's Happening:**

1. **Initial Phase (Tasks 1-20)**
   - System encounters various errors
   - No learned knowledge yet
   - Success rate: ~70-75%

2. **First Learning (Tasks 20-40)**
   - Patterns detected (5+ similar errors)
   - First knowledge items added
   - Skills updated automatically
   - Success rate jumps to 80-85%

3. **Continuous Improvement (Tasks 40-100)**
   - More patterns learned
   - Additional knowledge accumulated
   - Error rate decreases
   - Success rate reaches 90-95%

### **The Learning Curve:**

```
Success Rate
100% │                                  ............
     │                            ......
     │                      ......
 90% │                ......
     │          .....
     │    .....
 70% │...
     │
     └─────────────────────────────────────────────> Tasks
       0     20     40     60     80    100
           ↑        ↑
       Learning  More Learning
       Cycle 1   Cycles 2-3
```

---

## 🔍 Examine The Learning Data

### **Check Learning Database:**

```bash
# View recorded errors
cat data/simulation/errors.jsonl | head -5

# View learned knowledge
cat data/simulation/learned_knowledge.json

# View simulation results
ls data/simulation/results/
```

### **Compare Skill Versions:**

```bash
# View initial version (v1)
cat skills/email_writer/versions/v1_initial.md

# View after 100 tasks (v2)
cat skills/email_writer/versions/v2_after_100_tasks.md

# View after 500 tasks (v3)
cat skills/email_writer/versions/v3_after_500_tasks.md

# See what changed
diff skills/email_writer/versions/v1_initial.md \
     skills/email_writer/versions/v3_after_500_tasks.md
```

---

## 💡 Running Different Scenarios

### **Scenario 1: Quick Test (Fast)**
```bash
python simulator.py --tasks 50 --quiet
```

### **Scenario 2: Standard Run (5 min)**
```bash
python simulator.py --tasks 100
```

### **Scenario 3: Extended Learning (15 min)**
```bash
python simulator.py --tasks 500
```

### **Scenario 4: Full Maturity (30 min)**
```bash
python simulator.py --tasks 1000
```

### **Scenario 5: Low Error Rate**
```bash
python simulator.py --tasks 100 --error-rate 0.10
# Starts with only 10% errors
# May take longer to trigger learning
```

### **Scenario 6: High Error Rate**
```bash
python simulator.py --tasks 100 --error-rate 0.40
# Starts with 40% errors
# More learning opportunities
# Bigger improvement visible
```

---

## 📈 Metrics To Watch

### **Success Rate:**
- **Initial**: Typically 70-75% (depends on error rate)
- **After 100 tasks**: 85-90%
- **After 500 tasks**: 93-96%
- **Plateau**: ~95-98% (some errors inevitable)

### **Learning Cycles:**
- **First cycle**: Usually around task 15-30
- **Frequency**: Every 30-50 tasks
- **Total in 100 tasks**: 2-4 cycles
- **Total in 500 tasks**: 8-12 cycles

### **Knowledge Items:**
- **Per cycle**: 1-3 items typically
- **Total after 100 tasks**: 4-8 items
- **Total after 500 tasks**: 12-20 items
- **High-confidence only**: >60% threshold

---

## 🎓 Understanding The Output

### **Lines to Watch For:**

```bash
# Task progress
"Task 50/100 - Success rate: 85.0%"
   → Shows current interval success rate

# Learning trigger
"🎓 Learning cycle! Added 2 knowledge items"
   → System detected patterns and learned

# Error rate reduction
"📉 Error rate now: 16.0%"
   → Errors less likely due to learned knowledge

# Final improvement
"Improvement: +23.5% (33.6% relative)"
   → Shows absolute and relative gains
```

---

## 🔧 Advanced Usage

### **Using SkillForge Directly:**

```python
from skillforge import SkillForge

# Initialize
forge = SkillForge()

# Execute tasks
result = forge.execute("Write a professional email about project delays")
print(result)

# Check stats
forge.print_stats()

# Manual learning trigger
stats = forge.run_learning_cycle()
print(f"Learned: {stats}")
```

### **Integrate Into Your Code:**

```python
from skillforge import execute

# Simple one-liner
result = execute("Create a quarterly report from data.xlsx", 
                 files=["data.xlsx"])

if result.success:
    print(f"Created {len(result.outputs)} files")
else:
    print(f"Failed: {result.errors}")
```

---

## 📊 Analyzing Results

### **JSON Output Structure:**

```json
{
  "config": {
    "num_tasks": 100,
    "initial_error_rate": 0.25
  },
  "metrics": {
    "initial_success_rate": 0.70,
    "final_success_rate": 0.935,
    "improvement": 0.235,
    "total_errors": 15,
    "total_learning_cycles": 3,
    "total_knowledge_items": 5
  },
  "success_rate_over_time": [0.70, 0.80, 0.86, 0.90, ...],
  "errors_over_time": [3, 2, 1, 1, ...],
  "learning_cycles": [1, 1, 1, 0, ...]
}
```

### **Plot The Data (Optional):**

```python
import json
import matplotlib.pyplot as plt

# Load results
with open('data/simulation/results/simulation_TIMESTAMP.json') as f:
    results = json.load(f)

# Plot success rate
plt.plot(results['success_rate_over_time'])
plt.title('Success Rate Over Time')
plt.xlabel('Interval (10 tasks)')
plt.ylabel('Success Rate')
plt.show()
```

---

## 🎯 What To Look For

### **Successful Learning Indicators:**

1. ✅ **Success rate increases** - From 70-75% → 90-95%
2. ✅ **Error rate decreases** - Printed during simulation
3. ✅ **Learning cycles trigger** - "🎓 Learning cycle!" messages
4. ✅ **Knowledge accumulates** - Check learned_knowledge.json
5. ✅ **Plateau reached** - Success rate stabilizes at high level

### **Expected Timeline:**

```
Tasks 1-20:    Baseline performance, collecting data
Tasks 20-40:   First learning, noticeable improvement
Tasks 40-100:  Continued learning, reaching maturity
Tasks 100-500: Fine-tuning, approaching optimal
Tasks 500+:    Diminishing returns, mostly stable
```

---

## 🐛 Troubleshooting

### **No Learning Cycles Triggered:**

**Cause**: Not enough similar errors
**Fix**: Increase error rate or run more tasks
```bash
python simulator.py --tasks 200 --error-rate 0.30
```

### **Success Rate Not Improving:**

**Cause**: Error rate too low to detect patterns
**Fix**: Start with higher error rate
```bash
python simulator.py --tasks 100 --error-rate 0.35
```

### **Simulation Too Slow:**

**Cause**: Too many tasks or verbose output
**Fix**: Use --quiet flag
```bash
python simulator.py --tasks 500 --quiet
```

---

## 📚 Next Steps

### **1. Run The Simulator** (5 min)
```bash
python simulator.py --tasks 100
```

### **2. Examine The Results** (5 min)
```bash
cat data/simulation/learned_knowledge.json
```

### **3. Compare Skill Versions** (5 min)
```bash
diff skills/email_writer/versions/v1_initial.md \
     skills/email_writer/SKILL.md
```

### **4. Try Different Scenarios** (15 min)
- Low error rate
- High error rate
- Extended runs (500+ tasks)

### **5. Integrate Into Your Code** (30 min)
- Use SkillForge API
- Add your own skills
- Customize error types

---

## 🎉 Success Criteria

You'll know SkillForge is working when:

1. ✅ Simulation runs without errors
2. ✅ Success rate improves over time (visible in output)
3. ✅ Learning cycles trigger (see "🎓" messages)
4. ✅ Knowledge items accumulate (check JSON)
5. ✅ Skills have "Learned Knowledge" section (check SKILL.md)
6. ✅ Final success rate is 90%+ (for 100+ task runs)

---

## 📖 Further Reading

- `COMPLETE_GUIDE.md` - Full architecture explanation
- `WHERE_IS_SELF_IMPROVEMENT.md` - Line-by-line learning code explanation
- `CODEBASE_REVIEW.md` - Detailed code review and improvements
- `skills/email_writer/CHANGELOG.md` - Real example of skill evolution

---

## 🤝 Contributing

Want to add more skills or improve existing ones?

1. Create new skill directory: `skills/your_skill/`
2. Add SKILL.md with frontmatter
3. Run simulator to test
4. Watch it learn!

The system will automatically:
- Discover your skill
- Use it for relevant tasks
- Learn from errors and successes
- Update the skill file

No manual intervention needed!

---

**Ready to see cumulative learning in action?**

```bash
python simulator.py --tasks 100
```

**Watch SkillForge learn from every mistake and get better over time!** 🚀
