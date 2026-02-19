# SkillForge: Closed-Loop Reliability for AI Agents (Learning Guardrails From Failures)

Agents failing isn’t the problem.

The real production problem is **repeat failure**: the same missing constraint, the same vague query, the same “3 PM” without timezone, over and over—despite retries and prompt tweaks.

SkillForge is an exploration of a simple (but surprisingly rare) property in agent systems:

> **Experience should become an enforceable artifact that changes future execution.**

Not “we updated the prompt.” Not “someone wrote a runbook.” An explicit guardrail you can inspect, test, and roll back.

---

## The insight: learning that ships as an artifact

When people say “agents should learn,” it’s often ambiguous:

- Fine-tuning (slow, costly, opaque)
- Better prompting (fast, brittle)
- Human memory (tribal knowledge)

SkillForge focuses on a narrower claim:

> Many agent failures can be reduced quickly by learning **preventative rules**: *if signals indicate a likely failure, then apply a safe remediation before execution.*

This produces **white-box learning outputs**: rules with explicit **Condition → Action** structure.

---

## What SkillForge actually does

At a high level:

1. Load skills declaratively from `SKILL.md` (no Python subclassing required).
2. Execute tasks with an execution context.
3. Record outcomes (success/errors + context snapshot).
4. Detect repeated failure patterns.
5. Generate rules from a pattern library.
6. Apply those rules automatically on the next run (closed loop).

Core modules:

- `skillforge.py`: orchestrates execute → record outcomes → learn
- `learning.py`: aggregates errors and triggers rule generation
- `knowledge.py`: rule engine + `PATTERN_LIBRARY` (templates for failure → mitigation)

---

## A concrete walkthrough: timezone failures become a guardrail

In the included email scenario, one recurring failure mode is:

- the task mentions a time (“10 AM”, “3 PM”)
- but the context has no timezone

SkillForge learns a prevention rule that looks like:

- **Detect**: `task.description` matches a time regex, and `context.has_timezone == False`
- **Remediate**: set a default `context.timezone = "UTC"` and flag `timezone_added`

This is intentionally boring—because boring is testable.

---

## Real before/after metric from the repo’s stored scenario results

The repository already contains the captured run artifacts under `data/learning/`.

From `data/learning/scenario_email_results.json` (50 baseline eval tasks vs 50 eval tasks with learned rules, seed `20260208`):

| Metric | Baseline (no learning) | With learning | Delta |
|---|---:|---:|---:|
| Success rate | 66% | 96% | **+30 pp** |
| Failures | 17/50 | 2/50 | -15 |
| Rules applied | 0 | 28 | +28 |
| “Errors prevented” credit | 0 | 28 | +28 |

A sharper view is error-type reduction:

- `TimezoneError` decreased from **8** (baseline) to **0** (with learning)
- `SpamTriggerError` decreased from **6** (baseline) to **0** (with learning)

This isn’t “the model got better.” It’s “the system started enforcing a missing precondition before execution.”

---

## Why this matters (founder lens)

This approach is best understood as **reliability engineering for agents**:

- Guardrails are explicit, inspectable, and testable
- Improvements compound over time (failure → mitigation → prevention)
- The learning loop is measurable via ablation (with vs without rules)

A product-shaped version of this idea is what I’d call **Agent Reliability CI**:

- scenario-based evaluation
- regression detection
- rule impact tracking (benefit vs false positives)
- safe auto-remediation vs “suggest-only” actions

In other words: treat agent behavior like software quality, not magic.

---

## Honest limitations

- The included scenario uses **simulated constant-rate errors** to validate that improvements come from rules (not from “error decay” or memorization).
- The current learning mechanism generates rules from a **pattern library**, which means it’s strong at turning known failure types into guardrails, not discovering arbitrary new concepts.

That’s still useful: most production pain is recurring and pattern-shaped.

---

## Verification

The current repo state was validated with the full test suite:

- `python -m pytest -q` → **150 passed**

---

## If you’re building agents: a practical checklist

If you want your agent system to “improve over time,” ask:

- Where do failures get recorded?
- Can you group failures by type?
- Do you generate a reusable mitigation artifact?
- Does that mitigation apply automatically next time?
- Can you inspect and test what changed?

If the answer is “no,” your system isn’t learning—it’s just retrying.
