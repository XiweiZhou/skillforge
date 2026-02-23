#!/usr/bin/env python3
"""
SkillForge · Live Demo
──────────────────────
  skill  —  warm start    email-writer, template execution ready from day one
  forge  —  calibration   watches every execution, builds rules, enforces them

Acts:
  I    Tasks execute with zero rules.  Same errors repeat.
  II   Auto-learn fires mid-stream.    Rules appear.  Errors stop.
  III  A rule underperforms, degrades to dormant, then resurfaces.

Usage:
  python scenarios/demo.py [--speed 0-2] [--seed N]
  --speed 0   instant (CI / quick review)
  --speed 1   normal  (default)
  --speed 2   slow    (presentations)
"""

import sys, time, re, random, argparse, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from skillforge import SkillForge
from skills import BaseSkill, ExecutionContext, ExecutionResult, ExecutionStatus, SkillOutput
from knowledge import RuleStatus, Rule, RuleType, Condition, ConditionOperator, Action

import logging
logging.disable(logging.CRITICAL)   # keep output clean


# ── ANSI codes ────────────────────────────────────────────────────────────────
R   = "\033[0m"
B   = "\033[1m"
D   = "\033[2m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
CYN = "\033[96m"
GRY = "\033[90m"


def _vlen(s: str) -> int:
    """Visible length of a string (strips ANSI escape codes)."""
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


def _rpad(s: str, width: int) -> str:
    """Right-pad s to visible width, accounting for ANSI codes."""
    return s + " " * max(0, width - _vlen(s))


# ── Global speed knob (set from CLI, read by pause()) ─────────────────────────
_speed: float = 1.0


def pause(s: float):
    if _speed > 0:
        time.sleep(s * _speed)


def emit(text: str = "", end: str = "\n"):
    sys.stdout.write(text + end)
    sys.stdout.flush()


# ── Email simulator skill ─────────────────────────────────────────────────────
class EmailSimulatorSkill(BaseSkill):
    """
    Replaces the real email-writer for the demo.

    Injects realistic, rule-preventable errors based on task text.
    PREVENTION rules modify context before _execute_impl runs, so if a rule
    already set has_timezone=True, the TimezoneError doesn't fire.  This
    makes the skill a genuine test of whether rules are doing their job.
    """

    # (trigger_regex, context_prop_that_prevents, flag_that_prevents, base_rate)
    _ERRORS = {
        "TimezoneError":    (r"\d{1,2}\s*(am|pm)",           "has_timezone",  None,            0.55),
        "SpamTriggerError": (r"\b(free|urgent|exclusive)\b", None,            "potential_spam", 0.50),
        "AttachmentError":  (r"\b(attach|document|report)\b","has_attachment", None,            0.45),
    }

    def _execute_impl(self, context: ExecutionContext) -> ExecutionResult:
        task  = context.task_description
        flags = context.flags if isinstance(context.flags, set) else set(context.flags or [])
        errors = []

        for etype, (pat, prop, flag, rate) in self._ERRORS.items():
            if not re.search(pat, task, re.IGNORECASE):
                continue
            if prop and context.properties.get(prop):
                continue
            if flag and flag in flags:
                continue
            if random.random() < rate:
                errors.append(etype)

        if errors:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                errors=[f"{e}: simulated" for e in errors],
            )
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            output=SkillOutput({"body": "Email drafted."}, "email"),
        )


# ── Task pool ─────────────────────────────────────────────────────────────────
TASKS = [
    "Write an email about the meeting at 3 PM",
    "Draft an email with the attached report",
    "Compose a professional team introduction",
    "Send an email about the urgent free trial offer",
    "Write a follow-up email for the 10 AM call",
    "Draft an email about the project deadline at 5 PM",
    "Compose an email requesting the document update",
    "Write an email about the exclusive partnership offer",
    "Draft a professional email about the attached contract",
    "Send a meeting recap email for the 2 PM session",
    "Compose an email about tomorrow's 9 AM kickoff",
    "Write an email enclosing the report document",
]

# Layout widths (visible chars)
_W_TASK   = 46   # task description column
_W_OUT    = 22   # outcome column  (padded to align forge note)
_W_FORGE  = 14   # forge annotation column


# ── Demo ──────────────────────────────────────────────────────────────────────
class Demo:

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self._counter = 0
        self._stats   = {"act1": [0, 0], "act2": [0, 0]}   # [success, fail]

    # ── Forge setup ───────────────────────────────────────────────────────────

    def _build_forge(self) -> SkillForge:
        # Use an isolated temp dir so persistent state from prior runs
        # doesn't contaminate the demo (stale rules would skip learning).
        tmpdir = tempfile.mkdtemp(prefix="skillforge_demo_")
        forge = SkillForge(data_dir=tmpdir)
        # Tune so auto-learn triggers clearly during Act I
        forge._auto_learn_min_uncovered = 2
        forge._auto_learn_max_errors    = 8
        # Swap in simulator skill
        forge.skill_registry.skills["email_writer"] = EmailSimulatorSkill(
            "email_writer", forge.knowledge_base
        )
        return forge

    # ── Visual primitives ─────────────────────────────────────────────────────

    def _banner(self, forge: SkillForge):
        n_rules = len(forge.knowledge_base.rule_index)
        w = 64
        emit()
        emit(f"{BLU}  ╔{'═'*w}╗{R}")
        emit(f"{BLU}  ║{B}{'SkillForge · Live Demo':^{w}}{R}{BLU}║{R}")
        emit(f"{BLU}  ╠{'═'*w}╣{R}")
        emit(f"{BLU}  ║{R}  {B}skill{R}  {D}—{R}  warm start    "
             f"email-writer, template execution ready"
             f"{' '*(w-49)}{BLU}║{R}")
        emit(f"{BLU}  ║{R}  {B}forge{R}  {D}—{R}  calibration  "
             f"{n_rules} rules · learning from every failure"
             f"{' '*(w-49)}{BLU}║{R}")
        emit(f"{BLU}  ╚{'═'*w}╝{R}")
        emit()

    def _section(self, title: str, subtitle: str = ""):
        bar = "─" * max(0, 60 - len(title))
        emit()
        emit(f"  {BLU}{B}─── {title} {R}{GRY}{bar}{R}")
        if subtitle:
            emit(f"  {D}{subtitle}{R}")
        emit()

    def _forge_box(self, lines: list):
        """Print a highlighted forge event box, revealing line-by-line."""
        w = 54
        emit()
        emit(f"  {CYN}╔{'═'*w}╗{R}")
        for raw in lines:
            visible = re.sub(r"\033\[[0-9;]*m", "", raw)
            pad     = " " * max(0, w - len(visible) - 2)
            emit(f"  {CYN}║{R}  {raw}{pad}  {CYN}║{R}")
            pause(0.10)
        emit(f"  {CYN}╚{'═'*w}╝{R}")
        emit()

    def _status_dot(self, status: RuleStatus) -> str:
        return {
            RuleStatus.ACTIVE:    f"{GRN}●{R}",
            RuleStatus.PROBATION: f"{YLW}⚠{R}",
            RuleStatus.DORMANT:   f"{GRY}💤{R}",
        }.get(status, "?")

    # ── Task execution ────────────────────────────────────────────────────────

    def _run_task(self, task: str, forge: SkillForge, act: str) -> tuple:
        """
        Animate one task:  print label → dots → execute → overwrite with result.

        Returns (result, auto_learned_this_task).
        The forge note column shows what the forge did alongside the skill outcome.
        """
        self._counter += 1
        n      = self._counter
        label  = task[:_W_TASK]
        prefix = f"  [{n:02d}] {label:<{_W_TASK}}"

        # ① Print task label + animated dots
        emit(prefix, end="")
        for _ in range(3):
            emit(f"{GRY}·{R}", end="")
            pause(0.09)

        # ② Execute (auto-learn may fire inside here)
        cycles_before = forge.learning_engine.learning_cycles
        result        = forge.execute(task, skill_name="email_writer")
        auto_learned  = forge.learning_engine.learning_cycles > cycles_before

        # ③ Build outcome string
        if result.success:
            if result.rules_applied:
                rule = forge.knowledge_base.rule_index.get(result.rules_applied[0])
                rname = rule.name.replace("Prevent ", "") if rule else "rule"
                outcome = f"{GRN}✓{R}  {D}↳ {rname.lower()}{R}"
            else:
                outcome = f"{GRN}✓{R}"
            self._stats[act][0] += 1
        else:
            enames  = ", ".join(e.split(":")[0] for e in result.errors)
            outcome = f"{RED}✗{R}  {D}{enames}{R}"
            self._stats[act][1] += 1

        # ④ Forge annotation (right column)
        if auto_learned:
            forge_note = f"{CYN}⚡ LEARNING{R}"
        elif result.success and result.rules_applied:
            forge_note = f"{CYN}rule fired ✓{R}"
        elif not result.success:
            forge_note = f"{GRY}logged{R}"
        else:
            forge_note = f"{GRY}ok{R}"

        # ⑤ Overwrite with full line  (⟵ this is the "both at same time" reveal)
        out_padded   = _rpad(outcome,     _W_OUT)
        forge_padded = _rpad(forge_note,  _W_FORGE)
        full = f"\r{prefix}  {out_padded}  {D}│{R}  {forge_padded}"
        emit(full)

        return result, auto_learned

    # ── Learn event box ───────────────────────────────────────────────────────

    def _learn_box(self, forge: SkillForge):
        by_type: dict = {}
        for err in forge.learning_engine.error_repo.errors:
            by_type[err.error_type] = by_type.get(err.error_type, 0) + 1

        rules = forge.knowledge_base.get_rules("email_writer")

        lines = [f"{B}{CYN}⚡ FORGE AUTO-LEARN{R}",
                 f"{GRY}{'─'*52}{R}"]

        for etype, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
            rule_match = next((r for r in rules if r.source_error_type == etype), None)
            if rule_match:
                dot  = self._status_dot(rule_match.status)
                arrow = f"→  {rule_match.name:<22} [{rule_match.confidence:.2f}] {dot}"
            else:
                arrow = f"{GRY}→  no rule generated{R}"
            lines.append(f"  {etype:<28}  ×{cnt}   {arrow}")

        self._forge_box(lines)

    # ── Acts ──────────────────────────────────────────────────────────────────

    def _act1(self, forge: SkillForge):
        self._section(
            "ACT I  ·  no rules  ·  the system in the wild",
            "skill starts warm — templates ready, zero accumulated wisdom",
        )

        pool = TASKS * 4
        random.shuffle(pool)

        learned    = False
        task_count = 20

        for i in range(task_count):
            task   = pool[i % len(pool)]
            result, auto_learned = self._run_task(task, forge, "act1")
            pause(0.22)

            if auto_learned and not learned:
                learned = True
                self._learn_box(forge)
                pause(0.3)

        # Safety: if auto-trigger didn't fire, run it explicitly
        if not learned:
            forge.run_learning_cycle(min_frequency=2, min_confidence=0.3)
            self._learn_box(forge)

    def _act2(self, forge: SkillForge):
        self._section(
            "ACT II  ·  rules active  ·  wisdom in action",
            "same task patterns — forge now enforces what it learned",
        )

        pool = TASKS * 4
        random.shuffle(pool)

        for i in range(20):
            task = pool[i % len(pool)]
            self._run_task(task, forge, "act2")
            pause(0.15)

    def _act3(self, forge: SkillForge):
        self._section(
            "ACT III  ·  rule lifecycle  ·  adapt or retire",
            "a poorly-calibrated rule — what does the forge do with it?",
        )

        # Plant a weak rule (using PoorQueryError which is in PATTERN_LIBRARY)
        weak = Rule(
            id="rule_query_demo",
            name="Prevent Poor Query",
            rule_type=RuleType.PREVENTION,
            conditions=[Condition("task.description", ConditionOperator.MATCHES, r"^(what|how|why|when)")],
            actions=[Action("flag", "_flags", "vague_query")],
            source_error_type="PoorQueryError",
            confidence=0.55,
            description="Lifecycle demo rule",
        )
        forge.knowledge_base.add_rule("email_writer", weak)
        forge.knowledge_base.rule_index[weak.id] = weak

        dummy = {"task": {"description": "write email"}, "context": {}, "_flags": set()}

        emit(f"  {B}Rule planted:{R}  {weak.name}  "
             f"confidence={weak.confidence:.2f}  "
             f"{self._status_dot(weak.status)}  {GRN}ACTIVE{R}")
        emit()
        pause(0.5)

        # Fast-forward: 85% failure rate (clearly underperforming)
        for app in range(1, 17):
            weak.apply(dummy)
            weak.record_outcome(random.random() < 0.15)

            if app in (5, 10, 15, 16):
                sym_text = {
                    RuleStatus.ACTIVE:    f"{GRN}ACTIVE{R}",
                    RuleStatus.PROBATION: f"{YLW}PROBATION{R}",
                    RuleStatus.DORMANT:   f"{GRY}DORMANT{R}",
                }.get(weak.status, "UNKNOWN")
                dot = self._status_dot(weak.status)
                emit(f"  {D}after {app:2d} applications{R}  "
                     f"eff={weak.effectiveness:.2f}  conf={weak.confidence:.2f}  "
                     f"{dot}  {sym_text}")
                pause(0.4)

        emit()

        if weak.status == RuleStatus.DORMANT:
            emit(f"  {GRY}Rule is dormant — stops firing, preserved as knowledge.{R}")
            pause(0.7)

            emit(f"\n  {D}New PoorQueryErrors surfacing... auto-learn will resurrect it.{R}")
            pause(0.3)

            # Inject enough errors so PoorQueryError proportion clears min_confidence=0.3
            # (frequency / total_errors >= 0.3 requires outweighing accumulated I+II errors)
            for _ in range(10):
                forge.learning_engine.record_error(
                    skill_name="email_writer",
                    task_description="what is this",
                    error_type="PoorQueryError",
                    error_message="PoorQueryError: simulated for resurrection demo",
                )
                emit(f"{GRY} ·{R}", end="")
                pause(0.10)
            emit()

            forge.run_learning_cycle(min_frequency=2, min_confidence=0.3)
            pause(0.5)

            dot      = self._status_dot(weak.status)
            sym_text = {
                RuleStatus.ACTIVE:    f"{GRN}ACTIVE{R}",
                RuleStatus.PROBATION: f"{YLW}PROBATION{R}",
                RuleStatus.DORMANT:   f"{GRY}DORMANT{R}",
            }.get(weak.status, "UNKNOWN")

            emit(f"\n  {CYN}↺  Resurrected:{R}  conf={weak.confidence:.2f}  {dot}  {sym_text}")
        else:
            emit(f"  {GRY}Rule retained — effectiveness met threshold.{R}")

    # ── Results ───────────────────────────────────────────────────────────────

    def _results(self, forge: SkillForge):
        self._section("RESULTS")

        s1, f1 = self._stats["act1"]
        s2, f2 = self._stats["act2"]
        t1, t2 = s1 + f1, s2 + f2
        r1     = s1 / max(t1, 1)
        r2     = s2 / max(t2, 1)

        BAR_W = 26

        def bar(rate: float) -> str:
            n = int(BAR_W * rate)
            return f"{GRN}{'█' * n}{GRY}{'░' * (BAR_W - n)}{R}"

        emit(f"  Before rules   {bar(r1)}  {r1:>4.0%}  ({s1}/{t1} succeeded)")
        emit(f"  After  rules   {bar(r2)}  {r2:>4.0%}  ({s2}/{t2} succeeded)")
        emit()

        kb     = forge.knowledge_base.get_statistics()
        by_st  = kb.get("rules_by_status", {})
        learns = forge.learning_engine.learning_cycles
        delta  = (r2 - r1) * 100

        verdict = (f"{GRN}✓ effective{R}"   if delta > 10 else
                   f"{YLW}◌ promising{R}"  if delta > 0  else
                   f"{RED}✗ needs work{R}")

        a = by_st.get("active", 0)
        p = by_st.get("probation", 0)
        d = by_st.get("dormant", 0)

        emit(f"  Rules    {a} {GRN}●{R} active   {p} {YLW}⚠{R} probation   {d} {GRY}💤{R} dormant")
        emit(f"  Learns   {learns} auto-triggered")
        emit(f"  Δ        {delta:+.1f}pp   {verdict}")
        emit()

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self):
        forge = self._build_forge()

        self._banner(forge)
        pause(0.5)

        self._act1(forge)
        pause(0.4)

        self._act2(forge)
        pause(0.4)

        self._act3(forge)
        pause(0.4)

        self._results(forge)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SkillForge live demo")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="0 = instant · 1 = normal (default) · 2 = slow")
    ap.add_argument("--seed",  type=int,   default=42,
                    help="Random seed (default: 42)")
    args = ap.parse_args()

    _speed = args.speed
    Demo(seed=args.seed).run()
