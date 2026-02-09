#!/usr/bin/env python3
"""
SkillForge Skills - Declarative skill system with knowledge-aware execution

Skills are loaded from SKILL.md files (AgentSkills.io specification compliant).
No Python subclassing needed to add new skills.
"""

import importlib.util
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

import yaml

from knowledge import KnowledgeBase, RuleType

logger = logging.getLogger("Skills")


class ExecutionStatus(Enum):
    """Execution status values"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    REJECTED = "rejected"


class ExecutionContext:
    """
    Context for skill execution including knowledge.

    Dynamic properties replace hard-coded fields (has_timezone, has_attachment, etc.).
    Backward-compatible: context.has_timezone works via __getattr__ routing to properties.
    """

    _KNOWN_FIELDS = {
        'task_description', 'task_id', 'user_files', 'metadata',
        'properties', 'warnings', 'suggestions', 'applied_rules', 'flags',
    }

    def __init__(self, task_description: str, task_id: str,
                 user_files: Optional[List[str]] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 **kwargs):
        self.task_description = task_description
        self.task_id = task_id
        self.user_files = user_files or []
        self.metadata = metadata or {}
        self.properties: Dict[str, Any] = {}
        self.warnings: List[str] = []
        self.suggestions: List[str] = []
        self.applied_rules: List[str] = []
        self.flags: set = set()

        # Extra kwargs go into properties (backward compat for has_timezone=False, etc.)
        for key, value in kwargs.items():
            self.properties[key] = value

    def __getattr__(self, name: str) -> Any:
        """Fall back to properties dict for unknown attributes"""
        if name.startswith('_'):
            raise AttributeError(name)
        properties = self.__dict__.get('properties', {})
        if name in properties:
            return properties[name]
        return None

    def __setattr__(self, name: str, value: Any):
        """Route unknown attribute writes to properties after init"""
        if name in self._KNOWN_FIELDS or 'properties' not in self.__dict__:
            super().__setattr__(name, value)
        else:
            self.properties[name] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for rule matching"""
        context_dict = dict(self.properties)
        context_dict['warnings'] = self.warnings.copy()
        context_dict['suggestions'] = self.suggestions.copy()
        return {
            'task': {
                'description': self.task_description,
                'id': self.task_id,
            },
            'context': context_dict,
            '_applied_rules': self.applied_rules.copy(),
            '_flags': list(self.flags),
        }

    def update_from_dict(self, data: Dict[str, Any]):
        """Update context from rule application results"""
        if '_applied_rules' in data:
            self.applied_rules = data['_applied_rules']
        if '_flags' in data:
            self.flags = data['_flags'] if isinstance(data['_flags'], set) else set(data['_flags'])
        if 'context' in data:
            ctx = data['context']
            if 'warnings' in ctx:
                self.warnings = ctx['warnings']
            if 'suggestions' in ctx:
                self.suggestions = ctx['suggestions']
            if 'timezone' in ctx:
                self.properties['has_timezone'] = True
                self.metadata['timezone'] = ctx['timezone']


class SkillOutput:
    """Output from skill execution"""
    def __init__(self, content: Any, output_type: str,
                 metadata: Optional[Dict[str, Any]] = None):
        self.content = content
        self.output_type = output_type
        self.metadata = metadata or {}


@dataclass
class StepRecord:
    """Record of a single step in multi-step LLM execution."""
    step_number: int
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    recovery_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step': self.step_number,
            'tool_calls': self.tool_calls,
            'tool_results': self.tool_results,
            'errors': self.errors,
            'recovery_applied': self.recovery_applied,
        }


class ExecutionResult:
    """Result of skill execution"""
    def __init__(self, status: ExecutionStatus,
                 output: Optional[SkillOutput] = None,
                 errors: Optional[List[str]] = None,
                 warnings: Optional[List[str]] = None,
                 rules_applied: Optional[List[str]] = None,
                 execution_time_ms: float = 0.0,
                 context_snapshot: Optional[Dict] = None,
                 steps: Optional[List[StepRecord]] = None):
        self.status = status
        self.output = output
        self.errors = errors or []
        self.warnings = warnings or []
        self.rules_applied = rules_applied or []
        self.execution_time_ms = execution_time_ms
        self.context_snapshot = context_snapshot
        self.steps: List[StepRecord] = steps or []

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS


class BaseSkill(ABC):
    """Base class for all skills with knowledge integration"""

    def __init__(self, name: str, knowledge_base: KnowledgeBase):
        self.name = name
        self.knowledge_base = knowledge_base
        self.executions = 0
        self.successes = 0

    @property
    def success_rate(self) -> float:
        if self.executions == 0:
            return 0.0
        return self.successes / self.executions

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """
        Execute the skill with knowledge application.

        Pipeline: prevention rules -> execute -> validation rules -> record outcomes
        """
        start_time = datetime.now()
        self.executions += 1

        try:
            # Step 1: Apply prevention rules
            context = self._apply_knowledge(context, [RuleType.PREVENTION])

            # Step 2: Check for rejections
            if 'rejected' in context.flags or context.to_dict().get('_rejected'):
                return ExecutionResult(
                    status=ExecutionStatus.REJECTED,
                    errors=[context.to_dict().get('_rejection_reason', 'Rejected by rule')],
                    rules_applied=context.applied_rules,
                    context_snapshot=context.to_dict(),
                )

            # Step 3: Execute the actual skill logic
            result = self._execute_impl(context)

            # Step 4: Apply validation rules to output
            if result.success and result.output:
                result = self._validate_output(context, result)

            # Step 5: Record outcome for all applied rules
            for rule_id in context.applied_rules:
                self.knowledge_base.record_rule_outcome(rule_id, result.success)

            # Update statistics
            if result.success:
                self.successes += 1

            # Add timing
            end_time = datetime.now()
            result.execution_time_ms = (end_time - start_time).total_seconds() * 1000
            result.rules_applied = context.applied_rules
            result.context_snapshot = context.to_dict()

            return result

        except Exception as e:
            logger.error(f"Skill execution error: {e}")
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                errors=[str(e)],
                context_snapshot=context.to_dict(),
            )

    def _apply_knowledge(self, context: ExecutionContext,
                        rule_types: List[RuleType]) -> ExecutionContext:
        """Apply knowledge rules to context"""
        context_dict = context.to_dict()
        modified = self.knowledge_base.apply_rules(
            self.name, context_dict, rule_types
        )
        context.update_from_dict(modified)
        return context

    def _validate_output(self, context: ExecutionContext,
                        result: ExecutionResult) -> ExecutionResult:
        """Apply validation rules to output"""
        context = self._apply_knowledge(context, [RuleType.VALIDATION])
        result.warnings.extend(context.warnings)
        return result

    @abstractmethod
    def _execute_impl(self, context: ExecutionContext) -> ExecutionResult:
        """Implement actual skill logic - override in subclasses"""
        pass


# ---------------------------------------------------------------------------
# Declarative skill: driven by SKILL.md metadata + optional assets/templates
# ---------------------------------------------------------------------------

class DeclarativeSkill(BaseSkill):
    """
    A skill whose behavior is driven by SKILL.md metadata and optional assets.

    No Python subclassing needed. Users create a directory with SKILL.md and
    the engine handles execution, learning, and knowledge application.

    Execution priority:
      1. Custom handler (scripts/handler.py)
      2. LLM-powered (when llm_provider is configured and available)
      3. Template-based (keyword matching + template copy, fallback)
    """

    def __init__(self, name: str, knowledge_base: KnowledgeBase,
                 skill_metadata: Dict[str, Any], skill_dir: Path,
                 llm_provider=None, tool_registry=None):
        super().__init__(name, knowledge_base)
        self.skill_metadata = skill_metadata
        self.skill_dir = skill_dir
        self.description = skill_metadata.get('description', '')
        self.output_type = skill_metadata.get('metadata', {}).get('output_type', 'generic')
        self.triggers = skill_metadata.get('metadata', {}).get('triggers', [])
        self.context_fields = skill_metadata.get('metadata', {}).get('context_fields', {})
        self._templates = self._load_templates()
        self._handler = self._load_handler()
        self._llm_provider = llm_provider
        self._tool_registry = tool_registry
        self._max_steps = skill_metadata.get('metadata', {}).get('max_steps', 5)

        # Load tools declared in SKILL.md metadata.tools
        tool_names = skill_metadata.get('metadata', {}).get('tools', [])
        if tool_names and self._tool_registry:
            self._tool_registry.load_tools_for_skill(tool_names)

    def _load_templates(self) -> Dict[str, Any]:
        """Load output templates from assets/templates.yaml if present"""
        templates_path = self.skill_dir / "assets" / "templates.yaml"
        if templates_path.exists():
            return yaml.safe_load(templates_path.read_text()) or {}
        return {}

    def _load_handler(self) -> Optional[Callable]:
        """Load optional custom Python handler from scripts/handler.py"""
        handler_path = self.skill_dir / "scripts" / "handler.py"
        if handler_path.exists():
            spec = importlib.util.spec_from_file_location(
                f"skill_handler_{self.name}", handler_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'execute'):
                return module.execute
        return None

    def _execute_impl(self, context: ExecutionContext) -> ExecutionResult:
        """Execute using handler, LLM, or template fallback."""
        if self._handler:
            return self._handler(context, self.skill_metadata)

        if self._llm_provider and self._llm_provider.is_available():
            return self._execute_with_llm(context, max_steps=self._max_steps)

        return self._execute_with_templates(context)

    def _execute_with_llm(self, context: ExecutionContext,
                          max_steps: int = 5) -> ExecutionResult:
        """
        Execute using the configured LLM provider with multi-step loop.

        Loop: LLM call -> tool calls -> check results -> recovery -> repeat
        Exits when LLM returns final content (no tool_calls) or max_steps.
        """
        from llm import LLMRequest, ToolResult as LLMToolResult

        # Build tool schemas from registry
        tool_schemas = []
        if self._tool_registry:
            tool_schemas = [
                d.to_llm_schema()
                for d in self._tool_registry.get_definitions()
            ]

        request = LLMRequest(
            task_description=context.task_description,
            skill_name=self.name,
            skill_description=self.description,
            templates=self._templates,
            context=context.to_dict(),
            available_tools=tool_schemas,
        )

        steps: List[StepRecord] = []
        all_tool_results: List[LLMToolResult] = []
        response = None

        for step_num in range(1, max_steps + 1):
            # LLM call with accumulated tool results
            response = self._llm_provider.generate(
                request,
                tool_results=all_tool_results if all_tool_results else None,
            )

            # If no tool calls, LLM produced final output
            if not response.tool_calls or not self._tool_registry:
                break

            # Execute tool calls
            executor = self._tool_registry.get_executor()
            step_tool_results = executor.execute_all(response.tool_calls)

            # Separate successes from failures
            failed_results = [tr for tr in step_tool_results if not tr.success]
            step_errors = [tr.error for tr in failed_results if tr.error]
            recovery_applied = []

            # If tool failures, attempt knowledge-based recovery
            if failed_results:
                for tr in failed_results:
                    error_type = self._classify_tool_error(tr.error or "")
                    recovery_context = context.to_dict()
                    recovered = self.knowledge_base.get_recovery_actions(
                        self.name, recovery_context,
                    )
                    new_rules = [
                        r for r in recovered.get('_applied_rules', [])
                        if r not in context.applied_rules
                    ]
                    recovery_applied.extend(new_rules)

                    if new_rules:
                        context.update_from_dict(recovered)
                        request.context = context.to_dict()

            # Record step
            steps.append(StepRecord(
                step_number=step_num,
                tool_calls=[{'tool': tc.tool_name, 'args': tc.arguments,
                             'id': tc.call_id} for tc in response.tool_calls],
                tool_results=[{'id': tr.call_id, 'success': tr.success,
                               'error': tr.error} for tr in step_tool_results],
                errors=step_errors,
                recovery_applied=recovery_applied,
            ))

            # Accumulate all results for next LLM call
            all_tool_results.extend(step_tool_results)

            # Inject recovery info as synthetic tool result
            if recovery_applied:
                all_tool_results.append(LLMToolResult(
                    call_id=f"recovery_step_{step_num}",
                    success=True,
                    data={'recovery_rules': recovery_applied,
                          'message': 'Knowledge-based recovery applied'},
                ))

        # Post-loop: build result
        intent = (response.intent if response and response.intent
                  else self._parse_intent(context.task_description.lower()))
        output_content = (response.content if response and response.content
                          else {'content': f'Output for: {context.task_description}'})

        # Run flag-based validation
        validation_errors = self._validate(context)
        if validation_errors:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                errors=validation_errors,
                warnings=context.warnings,
                steps=steps,
            )

        output = SkillOutput(
            content=output_content,
            output_type=self.output_type,
            metadata={'intent': intent, 'warnings': context.warnings,
                      'llm_powered': True,
                      'steps_taken': len(steps) + 1},
        )

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            output=output,
            warnings=context.warnings,
            steps=steps,
        )

    def _classify_tool_error(self, error_message: str) -> str:
        """Classify a tool error message against known error types."""
        from knowledge import RuleGenerator
        error_lower = error_message.lower()
        for error_type in RuleGenerator.PATTERN_LIBRARY:
            base = error_type.replace('Error', '').lower()
            if base in error_lower:
                return error_type
        return 'GenericError'

    def _execute_with_templates(self, context: ExecutionContext) -> ExecutionResult:
        """Execute using keyword matching and template output (fallback)."""
        task = context.task_description.lower()

        # Parse intent from templates
        intent = self._parse_intent(task)

        # Generate output from template
        output_content = self._generate_output(task, intent, context)

        # Run flag-based validation
        validation_errors = self._validate(context)
        if validation_errors:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                errors=validation_errors,
                warnings=context.warnings,
            )

        output = SkillOutput(
            content=output_content,
            output_type=self.output_type,
            metadata={'intent': intent, 'warnings': context.warnings},
        )

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            output=output,
            warnings=context.warnings,
        )

    def _parse_intent(self, task: str) -> str:
        """Parse intent by matching task keywords against template match lists"""
        for intent_name, template in self._templates.items():
            match_keywords = template.get('match', [])
            if any(kw in task for kw in match_keywords):
                return intent_name

        # Return the last template key as default (convention: last = default)
        if self._templates:
            return list(self._templates.keys())[-1]
        return 'general'

    def _generate_output(self, task: str, intent: str,
                        context: ExecutionContext) -> Dict[str, Any]:
        """Generate output from template or generic fallback"""
        if intent in self._templates:
            template = self._templates[intent]
            result = {k: v for k, v in template.items() if k != 'match'}
        else:
            result = {'content': f'Output for: {task}'}

        result['generated_at'] = datetime.now().isoformat()

        # Apply timezone context if available
        if context.properties.get('has_timezone') and 'timezone' in context.metadata:
            if 'body' in result:
                result['body'] += f"\n\n(All times in {context.metadata['timezone']})"

        if context.warnings:
            result['notes'] = context.warnings

        return result

    def _validate(self, context: ExecutionContext) -> List[str]:
        """Run flag-based validation checks"""
        errors = []

        # Attachment validation: flagged but not provided
        if 'attachment_mentioned' in context.flags:
            if not context.properties.get('has_attachment'):
                errors.append("Email mentions attachment but none provided")

        # Scheduling conflict validation
        if 'scheduling_conflict' in context.flags:
            if context.properties.get('has_conflict'):
                errors.append("Scheduling conflict detected")

        return errors

    def get_default_context_values(self) -> Dict[str, Any]:
        """Get default property values from SKILL.md context_fields"""
        defaults = {}
        for field_name, field_def in self.context_fields.items():
            if isinstance(field_def, dict) and 'default' in field_def:
                defaults[field_name] = field_def['default']
        return defaults


# ---------------------------------------------------------------------------
# Skill loading from disk
# ---------------------------------------------------------------------------

class SkillLoader:
    """Loads skills from directories containing SKILL.md files"""

    @classmethod
    def load_all(cls, knowledge_base: KnowledgeBase,
                 skills_dir: Path, llm_provider=None,
                 tool_registry=None) -> Dict[str, BaseSkill]:
        """Scan skills directory and load each skill from its SKILL.md"""
        skills = {}

        if not skills_dir.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return skills

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            try:
                skill = cls._load_skill(skill_dir, knowledge_base,
                                        llm_provider=llm_provider,
                                        tool_registry=tool_registry)
                if skill:
                    skills[skill.name] = skill
                    logger.info(f"Loaded skill: {skill.name} from {skill_dir.name}/")
            except Exception as e:
                logger.error(f"Failed to load skill from {skill_dir}: {e}")

        return skills

    @classmethod
    def _load_skill(cls, skill_dir: Path,
                    knowledge_base: KnowledgeBase,
                    llm_provider=None,
                    tool_registry=None) -> Optional[BaseSkill]:
        """Load a single skill from its directory"""
        skill_md = skill_dir / "SKILL.md"
        frontmatter = cls._parse_frontmatter(skill_md.read_text())

        spec_name = frontmatter.get('name')
        if not spec_name:
            logger.error(f"SKILL.md missing 'name' in {skill_dir}")
            return None
        if not frontmatter.get('description'):
            logger.error(f"SKILL.md missing 'description' in {skill_dir}")
            return None

        # Internal name: convert hyphenated spec name to underscored
        # (preserves backward compat with rules.json, error repos, etc.)
        internal_name = spec_name.replace('-', '_')

        return DeclarativeSkill(
            name=internal_name,
            knowledge_base=knowledge_base,
            skill_metadata=frontmatter,
            skill_dir=skill_dir,
            llm_provider=llm_provider,
            tool_registry=tool_registry,
        )

    @staticmethod
    def _parse_frontmatter(text: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from markdown file"""
        if not text.startswith('---'):
            return {}
        parts = text.split('---', 2)
        if len(parts) < 3:
            return {}
        return yaml.safe_load(parts[1]) or {}


# ---------------------------------------------------------------------------
# Skill registry
# ---------------------------------------------------------------------------

class SkillRegistry:
    """Registry of available skills - loads from skill directories"""

    def __init__(self, knowledge_base: KnowledgeBase,
                 skills_dir: Optional[Path] = None,
                 llm_provider=None, tool_registry=None):
        self.knowledge_base = knowledge_base
        self.skills: Dict[str, BaseSkill] = {}
        self._trigger_index: Dict[str, str] = {}

        # Load skills from disk
        skills_dir = skills_dir or Path(__file__).parent / "skills"
        loaded = SkillLoader.load_all(knowledge_base, skills_dir,
                                      llm_provider=llm_provider,
                                      tool_registry=tool_registry)
        for skill in loaded.values():
            self.register(skill)

    def register(self, skill: BaseSkill):
        """Register a skill and index its triggers"""
        self.skills[skill.name] = skill

        if isinstance(skill, DeclarativeSkill):
            for trigger in skill.triggers:
                self._trigger_index[trigger.lower()] = skill.name

        logger.info(f"Registered skill: {skill.name}")

    def get(self, name: str) -> Optional[BaseSkill]:
        """Get a skill by name"""
        return self.skills.get(name)

    def get_for_task(self, task: str) -> Optional[BaseSkill]:
        """Get the best skill for a task.

        Scores each skill by (number of trigger matches, earliest position).
        More matches wins; ties broken by which trigger appears first in the task.
        """
        task_lower = task.lower()
        # skill_name -> (match_count, earliest_position)
        scores: Dict[str, List[int]] = {}
        for trigger, skill_name in self._trigger_index.items():
            pos = task_lower.find(trigger)
            if pos >= 0:
                if skill_name not in scores:
                    scores[skill_name] = [0, pos]
                scores[skill_name][0] += 1
                scores[skill_name][1] = min(scores[skill_name][1], pos)
        if not scores:
            return None
        # Sort by: most matches DESC, earliest position ASC
        best = min(scores, key=lambda s: (-scores[s][0], scores[s][1]))
        return self.skills.get(best)

    def list_skills(self) -> List[str]:
        """List all registered skills"""
        return list(self.skills.keys())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from knowledge import KnowledgeBase, RuleGenerator

    kb = KnowledgeBase(Path("./data/learning"))
    generator = RuleGenerator()

    # Add a timezone rule
    rule = generator.generate_rule_from_error("TimezoneError", frequency=5, confidence=0.75)
    if rule:
        kb.add_rule("email_writer", rule)

    # Create skill registry (loads from skills/ directory)
    registry = SkillRegistry(kb)
    print(f"Loaded skills: {registry.list_skills()}")

    # Create execution context with dynamic properties
    context = ExecutionContext(
        task_description="Write an email about meeting at 2 PM tomorrow",
        task_id="test_001",
        has_timezone=False,
    )

    # Get skill and execute
    skill = registry.get("email_writer")
    if skill:
        result = skill.execute(context)
        print(f"Status: {result.status.value}")
        print(f"Rules applied: {result.rules_applied}")
        print(f"Warnings: {result.warnings}")
        if result.output:
            print(f"Output: {result.output.content}")

    kb.save_rules()
