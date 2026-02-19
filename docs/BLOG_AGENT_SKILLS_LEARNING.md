# From Prompt Tweaks to Learning Machines: The Agent Skill Primitive

Last week I posted about OpenClaw pulling news, analyzing a market meltdown, and building an infographic in 10 minutes. The response surprised me — a lot of people asked the same question: *how does it actually know how to do that?*

That question is worth a proper answer. Not just "it uses Claude" — that's like saying a car works because of combustion. The more interesting answer is about the **skill primitive**: the unit of capability that sits between raw LLM intelligence and reliable agent behavior. And there's a property most current systems are missing that changes everything: skills that learn.

This is what SkillForge is exploring.

---

## A Brief History of How We Got Here

To understand why agent skills matter, you need to see the problem they're solving.

**2022: The Prompting Era**

Before tool use, agents were purely language outputs. You prompted, the model responded. Smart prompt engineering was the entire craft. Results were non-deterministic, couldn't touch external systems, and every "improvement" was tribal knowledge — someone on the team knew the prompt incantation that worked.

**October 2022: ReAct Changes the Mental Model**

The [ReAct paper](https://arxiv.org/abs/2210.03629) (Reason + Act) demonstrated something crucial: interleaving chain-of-thought reasoning with tool calls produced dramatically better results than either alone. The model could now *think about* what to do, *do it*, observe the result, and reason about what to do next.

```
Thought: I need to find recent news about the CrowdStrike outage
Action: web_search("CrowdStrike BSOD July 2024")
Observation: [results...]
Thought: Now I need to quantify the financial impact
Action: web_search("CrowdStrike financial impact estimate")
...
```

This is the foundation every agentic framework since is built on. OpenAI's function calling, Anthropic's tool use — all ReAct in production clothing.

**2023: The Framework Explosion (and the Learning Gap)**

LangChain, AutoGPT, BabyAGI, LlamaIndex — suddenly everyone was building agents. But something subtle was missing: none of them could genuinely learn. They could retry. They could use memory buffers. But when the session ended, accumulated error knowledge evaporated. Every new run started fresh, ready to make the same mistakes again.

**2024–2025: Standardization Arrives**

Model Context Protocol (MCP) standardized how agents talk to tools. AgentSkills.io defined how to declare what an agent can do. Claude Code shipped with a skills architecture. The *interface* layer got solved. But the **learning** layer remained largely unaddressed.

**The question nobody had fully answered**: once an agent makes a mistake, how does that mistake durably change how the next task runs?

---

## The Challenge Engineers Are Hitting Right Now

If you're building production agents, you've probably run into at least three of these:

**The Retry Trap.** You add retry logic. Errors go down. Until they don't. Because retry doesn't fix root causes — it just runs the same broken logic again with fresh optimism. The timezone is still missing. The spam trigger words are still in the output.

**Prompt Drift.** You notice a class of failures, so you update the system prompt. It works. Six weeks later, someone else changes the prompt for a different reason, and the timezone fix is silently broken. Nobody knows what changed or why.

**The No-Baseline Problem.** You ship an "improvement." Was it actually better? By how much? On what task distribution? Most teams have no answer — because there's no ablation infrastructure for agents.

**Repeat Failures at Scale.** Your demo works. Your production handles 5,000 tasks per day. Suddenly the 0.5% edge case that never showed up in testing is 25 failures a day. And they're all the same edge case, over and over, because the system has no way to generalize from the first occurrence to prevent the rest.

**White-Box vs Black-Box Improvement.** Fine-tuning is expensive, slow, and opaque. When the model gets better, you don't know which inputs drove the improvement or which failure modes are now handled. You can't inspect, test, or roll back a fine-tune the way you can a code change.

SkillForge was designed specifically to address these. The mechanism is what I want to show.

---

## The Skill Primitive: Three Lines of YAML, One Unit of Capability

In SkillForge, a skill is defined by a single `SKILL.md` file. This is the entire `email-writer` skill definition header:

```yaml
---
name: email-writer
description: >-
  Writes professional emails based on user intent. Handles spam detection,
  timezone awareness, and attachment management.
metadata:
  triggers:
    - email
    - write email
    - compose
    - draft email
  output_type: email
  context_fields:
    has_timezone: { type: bool, default: false }
    has_attachment: { type: bool, default: false }
---
```

No Python subclassing. No framework boilerplate. The engine reads this file, auto-discovers the skill, matches incoming tasks via triggers, and wires up the entire execution + learning loop automatically.

Drop a new `SKILL.md` in `skills/my-new-skill/` and it exists. That's the skill primitive as a *declaration*.

### Three-Tier Execution

The engine doesn't just call the LLM for everything. It uses a tiered approach:

```
Incoming task
    │
    ▼
[1] Custom handler.py?  → run it (fastest, most deterministic)
    │
    ▼
[2] LLM available?      → multi-step tool-calling loop (most capable)
    │
    ▼
[3] Fallback             → template matching (always works)
```

This matters for reliability. The best-effort path (LLM) handles complexity. The fallback path (templates) means the skill never completely fails to produce output. And custom handlers let you wire in deterministic logic for the things that should never be non-deterministic.

### Multi-Step Execution

When the LLM path runs, it's not a single prompt → single response. It's a loop:

```
for step in range(max_steps):
    response = llm.generate(system_prompt, history, tools)

    if response.has_tool_calls:
        tool_results = execute_tools(response.tool_calls)
        history.append(tool_results)
        continue  # next step

    break  # final response
```

Each step accumulates tool results. The LLM sees what it retrieved, what failed, what it needs to try next. This is why OpenClaw can pull news, analyze it, and produce an output in sequence — it's not one magic call, it's a bounded iteration loop where each step informs the next.

---

## The Learning Loop: Where the Magic Actually Happens

Here's the part most systems skip. Execution produces outcomes. Outcomes contain signal. That signal, if captured and acted on, can change future execution.

The loop looks like this:

```
Task Description
    │
    ▼
[Apply Rules]  ← knowledge accumulated from past failures
    │
    ▼
Execute
    │
    ▼
Outcome (success or failure + context snapshot)
    │
    ▼
Pattern Detection (if failure: does this look like a known error class?)
    │
    ▼
Rule Generation (Condition → Action)
    │
    ▼
Knowledge Base (persisted to disk, loaded next run)
    │
    └──────────────────────────────────────────────────┐
                                                        │
                                              [Apply Rules] on next task
```

The knowledge base doesn't live in memory between sessions. It's written to `data/learning/rules.json`. Every new task execution starts by loading accumulated rules and checking which ones apply.

### A Concrete Example: The Timezone Story

The email-writer skill gets tasks like:

- "Write an email about the meeting at 3 PM"
- "Draft a follow-up email for the 10 AM call"

These tasks mention times. But without a timezone, the generated email is ambiguous or wrong. In production, this is a `TimezoneError` — and it happens 40% of the time on time-mentioning tasks.

**Step 1: Failure accumulates**

The learning engine records each failure with full context:

```json
{
  "task": "Draft a follow-up email for the 10 AM call",
  "error_type": "TimezoneError",
  "context": { "has_timezone": false },
  "timestamp": "2026-02-08T..."
}
```

**Step 2: Pattern detection**

After 50 training tasks, `LearningEngine.run_learning_cycle()` scans the error log. It finds: `TimezoneError` appeared frequently, it has a template in the `PATTERN_LIBRARY`, frequency and confidence both pass threshold.

**Step 3: Rule generation**

`RuleGenerator` instantiates the rule from the pattern library template:

```python
PATTERN_LIBRARY = {
    'TimezoneError': {
        'detection': [
            Condition('task.description', MATCHES, r'\d{1,2}\s*(am|pm|AM|PM)'),
            Condition('context.has_timezone', EQUALS, False),
        ],
        'remediation': [
            Action('add_field', 'context.timezone', 'UTC'),
            Action('flag', '_flags', 'timezone_added'),
        ],
        ...
    }
}
```

This generates a `Rule` object: an explicit `Condition → Action` artifact with a confidence score, application count, and effectiveness tracking.

**Step 4: Prevention**

Next time a task arrives: "Send an email about the 2 PM meeting" — before execution, the knowledge base evaluates all applicable rules against the context:

```python
# knowledge.py: KnowledgeBase.apply_rules()
applicable = self.get_applicable_rules(skill_name, context)
for rule in applicable:
    context = rule.apply(context)  # sets timezone, adds flag
```

The rule fires. `context.timezone` is set to UTC. The email gets generated with a timezone. `TimezoneError` never occurs.

**Step 5: Outcome feedback**

If the task succeeds after the rule was applied, the rule's effectiveness score increases via a Bayesian update:

```python
# knowledge.py: Rule.record_outcome()
self.confidence = (self.confidence * 0.7) + (self.effectiveness * 0.3)
```

Rules that work get higher confidence. Rules that don't degrade and eventually stop firing.

---

## The Demo: Watching the Loop Close

You can run this yourself. Clone the repo, create the venv, then:

```bash
python3 scenarios/scenario_email.py
```

The scenario runs three phases with a **constant error injection rate** — errors don't decay over time by design. Improvement can only come from rules actually working.

**Phase 1: Training (50 tasks, no rules)**
```
Training task 10/50: 12 errors collected
Training task 20/50: 24 errors collected
...
Error types: {'TimezoneError': 8, 'SpamTriggerError': 6, 'AttachmentError': 3}
```

**Phase 2: Learning**
```
Patterns detected: 3
Rules generated: 6  (prevention + recovery for each pattern)
Rule: Prevent Timezone (confidence: 0.80)
  Conditions: ["task.description matches '\\d{1,2}\\s*(am|pm)'", "context.has_timezone equals false"]
```

**Phase 3: Ablation evaluation (50 tasks each, baseline vs learned)**
```
EVALUATION WITHOUT LEARNING (BASELINE):
  Success rate: 66%
  Failures: 17/50

EVALUATION WITH LEARNING:
  Success rate: 96%
  Failures: 2/50
  Rules applied: 28
  Errors prevented: 28
```

The critical thing: `TimezoneError` goes from **8 failures** to **0**. `SpamTriggerError` goes from **6** to **0**. Not because the model got better — because the system started enforcing a missing precondition before execution ran.

And you can read exactly what changed. Open `data/learning/rules.json`:

```json
{
  "email_writer": [
    {
      "id": "rule_timezoneerror_1",
      "name": "Prevent Timezone",
      "rule_type": "prevention",
      "conditions": [
        { "field": "task.description", "operator": "matches", "value": "\\d{1,2}\\s*(am|pm|AM|PM)" },
        { "field": "context.has_timezone", "operator": "equals", "value": false }
      ],
      "actions": [
        { "action_type": "add_field", "target": "context.timezone", "value": "UTC" },
        { "action_type": "flag", "target": "_flags", "value": "timezone_added" }
      ],
      "confidence": 0.80,
      "times_applied": 28,
      "times_successful": 27
    }
  ]
}
```

This is white-box learning. You can inspect it, test it, roll it back, add it to version control, and diff it like code. Compare that to "we updated the system prompt" or "we fine-tuned on more data."

---

## Three Rule Types: Prevention, Validation, Recovery

The knowledge system handles three distinct phases of the execution lifecycle:

**PREVENTION** rules apply *before* execution. They modify the context so the task runs correctly from the start. The timezone rule is a prevention rule.

**VALIDATION** rules apply *after* execution. They check that output meets quality criteria — no spam trigger words, required fields present, format correct.

**RECOVERY** rules fire *mid-execution* when a tool call fails. The engine catches the failure, applies recovery rules to the context, and injects a synthetic tool result so the LLM sees what remediation was attempted:

```python
# skills.py: DeclarativeSkill._execute_with_llm()
if tool_result.is_error:
    recovered_context = self.knowledge_base.get_recovery_actions(skill_name, context)
    # inject recovery as synthetic tool result so LLM sees what happened
    tool_results.append(ToolResult(
        tool_call_id=tc.id,
        content=f"[Recovery applied: {recovery_info}] {tool_result.content}"
    ))
```

The LLM doesn't just see "tool failed." It sees "tool failed, recovery applied: timezone was missing, defaulted to UTC." It can reason about the recovery and continue intelligently.

---

## The Key Architectural Insight

Most agent systems treat the LLM as both the intelligence and the reliability mechanism. That creates a coupling that's hard to untangle. If something goes wrong, your only levers are: better prompts, more examples, bigger model.

SkillForge separates these concerns:

- **The LLM** provides general language intelligence and tool orchestration
- **The skill** defines the contract: what triggers this capability, what context it needs, what output it produces
- **The knowledge base** enforces preconditions and postconditions learned from experience

The knowledge base is the part that compounds. Every failure that crosses a frequency threshold becomes a rule. Every rule application that succeeds increases confidence. Every skill run contributes to a shared pool of accumulated knowledge that every future run inherits.

This is the property OpenClaw-like systems need: not just the ability to execute, but the ability to get systematically better at executing — without human intervention, without fine-tuning, and with full auditability of what changed and why.

---

## What's Not Solved (Yet)

To be honest about the current state:

- The `PATTERN_LIBRARY` is hand-curated. The system is excellent at generalizing known error types into rules, but it can't yet invent entirely new error categories from scratch.
- Cross-skill learning doesn't happen — a lesson learned by `email-writer` doesn't automatically transfer to `content-summarizer`.
- The current confidence model is a simple exponential decay Bayesian update. It works, but causal inference would produce much more precise rules.

These are the next frontiers. The primitives are in place; the sophistication of the learning mechanism is what scales them.

---

## If You Want to Go Deeper

The code is all here in this repo:

- `knowledge.py` — `Condition`, `Action`, `Rule`, `KnowledgeBase`, and the `PATTERN_LIBRARY`
- `learning.py` — `ErrorRecord`, `PatternDetector`, `LearningEngine`
- `skills.py` — `DeclarativeSkill`, `SkillLoader`, multi-step execution loop
- `skillforge.py` — the orchestrator that wires it all together
- `scenarios/scenario_email.py` — the demo you can run end-to-end

Start with `scenario_email.py`. Run it. Look at what gets written to `data/learning/`. Then read `knowledge.py` to see how those rules get applied on the next execution. The loop is small enough to hold in your head, and concrete enough to instrument and extend.

That's how OpenClaw's 10-minute infographic works. Not magic — a composable skill primitive, a reliable execution loop, and knowledge that accumulates instead of evaporating.

---

*SkillForge is an open exploration of self-improving agent systems. The repo is at [github.com/XiweiZhou/skillforge] — pull requests and failure reports both welcome.*
