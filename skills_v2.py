#!/usr/bin/env python3
"""
SkillForge Skills v2
Real skill implementations with knowledge-aware execution
"""

import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum

from knowledge import KnowledgeBase, Rule, RuleType

logger = logging.getLogger("Skills")


class ExecutionStatus(Enum):
    """Execution status values"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    REJECTED = "rejected"


@dataclass
class ExecutionContext:
    """Context for skill execution including knowledge"""
    task_description: str
    task_id: str
    user_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Knowledge-related
    has_timezone: bool = False
    has_attachment: bool = False
    has_conflict: bool = False
    violates_preferences: bool = False
    avg_credibility: float = 0.5

    # Runtime state
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    applied_rules: List[str] = field(default_factory=list)
    flags: set = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for rule matching"""
        return {
            'task': {
                'description': self.task_description,
                'id': self.task_id,
            },
            'context': {
                'has_timezone': self.has_timezone,
                'has_attachment': self.has_attachment,
                'has_conflict': self.has_conflict,
                'violates_preferences': self.violates_preferences,
                'avg_credibility': self.avg_credibility,
                'warnings': self.warnings.copy(),
                'suggestions': self.suggestions.copy(),
            },
            '_applied_rules': self.applied_rules.copy(),
            '_flags': list(self.flags),  # Convert set to list for JSON
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
                self.has_timezone = True
                self.metadata['timezone'] = ctx['timezone']


@dataclass
class SkillOutput:
    """Output from skill execution"""
    content: Any  # The actual output (email text, calendar event, etc.)
    output_type: str  # "email", "calendar_event", "search_results", etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result of skill execution"""
    status: ExecutionStatus
    output: Optional[SkillOutput] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rules_applied: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

    # For learning feedback
    context_snapshot: Optional[Dict] = None

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
        Execute the skill with knowledge application

        This is the main entry point that:
        1. Applies pre-execution rules
        2. Runs the actual skill logic
        3. Applies validation rules
        4. Records outcomes for learning
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

        # Apply rules
        modified = self.knowledge_base.apply_rules(
            self.name, context_dict, rule_types
        )

        # Update context from modified dict
        context.update_from_dict(modified)

        return context

    def _validate_output(self, context: ExecutionContext,
                        result: ExecutionResult) -> ExecutionResult:
        """Apply validation rules to output"""
        # Apply validation rules
        context = self._apply_knowledge(context, [RuleType.VALIDATION])

        # Check for validation warnings
        result.warnings.extend(context.warnings)

        return result

    @abstractmethod
    def _execute_impl(self, context: ExecutionContext) -> ExecutionResult:
        """Implement actual skill logic - override in subclasses"""
        pass


class EmailWriterSkill(BaseSkill):
    """Email writing skill with knowledge-aware execution"""

    def __init__(self, knowledge_base: KnowledgeBase):
        super().__init__("email_writer", knowledge_base)

    def _execute_impl(self, context: ExecutionContext) -> ExecutionResult:
        """Generate an email based on task description"""
        task = context.task_description.lower()

        # Parse intent
        intent = self._parse_intent(task)

        # Generate email content
        email_content = self._generate_email(task, intent, context)

        # Validate email
        validation_errors = self._validate_email(email_content, context)

        if validation_errors:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                errors=validation_errors,
                warnings=context.warnings,
            )

        output = SkillOutput(
            content=email_content,
            output_type="email",
            metadata={
                'intent': intent,
                'has_timezone': context.has_timezone,
                'warnings': context.warnings,
            }
        )

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            output=output,
            warnings=context.warnings,
        )

    def _parse_intent(self, task: str) -> str:
        """Determine email intent from task description"""
        if 'meeting' in task or 'schedule' in task:
            return 'meeting_request'
        elif 'follow' in task or 'recap' in task:
            return 'follow_up'
        elif 'introduce' in task or 'introduction' in task:
            return 'introduction'
        elif 'decline' in task or 'cancel' in task:
            return 'decline'
        elif 'thank' in task:
            return 'thank_you'
        else:
            return 'general'

    def _generate_email(self, task: str, intent: str,
                       context: ExecutionContext) -> Dict[str, str]:
        """Generate email content"""
        # Base templates by intent
        templates = {
            'meeting_request': {
                'subject': 'Meeting Request',
                'body': 'I would like to schedule a meeting to discuss...'
            },
            'follow_up': {
                'subject': 'Follow-up on our previous discussion',
                'body': 'Following up on our recent conversation...'
            },
            'introduction': {
                'subject': 'Introduction',
                'body': 'I wanted to take a moment to introduce...'
            },
            'decline': {
                'subject': 'Re: Meeting Request',
                'body': 'Thank you for the invitation. Unfortunately...'
            },
            'thank_you': {
                'subject': 'Thank You',
                'body': 'I wanted to express my appreciation for...'
            },
            'general': {
                'subject': 'Regarding your request',
                'body': 'I am writing to address...'
            }
        }

        template = templates.get(intent, templates['general'])

        email = {
            'subject': template['subject'],
            'body': template['body'],
            'generated_at': datetime.now().isoformat(),
        }

        # Apply context modifications
        if context.has_timezone and 'timezone' in context.metadata:
            # Modify body to include timezone
            email['body'] += f"\n\n(All times in {context.metadata['timezone']})"

        # Add warnings as notes
        if context.warnings:
            email['notes'] = context.warnings

        return email

    def _validate_email(self, email: Dict, context: ExecutionContext) -> List[str]:
        """Validate generated email"""
        errors = []

        # Check for spam triggers if flagged
        if 'potential_spam' in context.flags:
            # In real implementation, would check and possibly rewrite
            # For now, pass with warning
            pass

        # Check for attachment mention if flagged
        if 'attachment_mentioned' in context.flags:
            if not context.has_attachment:
                errors.append("Email mentions attachment but none provided")

        return errors


class CalendarManagerSkill(BaseSkill):
    """Calendar management skill with knowledge-aware execution"""

    def __init__(self, knowledge_base: KnowledgeBase):
        super().__init__("calendar_manager", knowledge_base)

    def _execute_impl(self, context: ExecutionContext) -> ExecutionResult:
        """Schedule a calendar event"""
        task = context.task_description.lower()

        # Parse meeting details
        meeting_info = self._parse_meeting_details(task, context)

        # Check for conflicts (using context)
        if context.has_conflict and 'scheduling_conflict' in context.flags:
            return ExecutionResult(
                status=ExecutionStatus.FAILURE,
                errors=["Scheduling conflict detected"],
                warnings=context.warnings,
            )

        # Check preferences
        if context.violates_preferences and 'preference_violation' in context.flags:
            # Add warning but continue
            context.warnings.append("This time may not align with participant preferences")

        # Create event
        event = {
            'title': meeting_info.get('title', 'Meeting'),
            'duration': meeting_info.get('duration', 60),
            'participants': meeting_info.get('participants', []),
            'created_at': datetime.now().isoformat(),
        }

        output = SkillOutput(
            content=event,
            output_type="calendar_event",
            metadata={'warnings': context.warnings}
        )

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            output=output,
            warnings=context.warnings,
        )

    def _parse_meeting_details(self, task: str,
                               context: ExecutionContext) -> Dict[str, Any]:
        """Parse meeting details from task"""
        details = {}

        # Extract duration
        duration_match = re.search(r'(\d+)\s*(hour|hr|minute|min)', task)
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2)
            if 'hour' in unit or 'hr' in unit:
                details['duration'] = amount * 60
            else:
                details['duration'] = amount
        else:
            details['duration'] = 60  # Default

        # Extract title hints
        if 'sync' in task:
            details['title'] = 'Team Sync'
        elif 'retrospective' in task:
            details['title'] = 'Retrospective'
        elif '1-on-1' in task or 'one-on-one' in task:
            details['title'] = '1:1 Meeting'
        else:
            details['title'] = 'Meeting'

        return details


class WebSearcherSkill(BaseSkill):
    """Web search skill with knowledge-aware execution"""

    def __init__(self, knowledge_base: KnowledgeBase):
        super().__init__("web_searcher", knowledge_base)

    def _execute_impl(self, context: ExecutionContext) -> ExecutionResult:
        """Execute a web search"""
        query = context.task_description

        # Check for vague query warning
        if 'vague_query' in context.flags:
            context.suggestions.append("Consider adding more specific terms to your query")

        # Simulate search (in real implementation, would call API)
        results = self._perform_search(query)

        # Check credibility
        if context.avg_credibility < 0.5 and 'low_credibility_sources' in context.flags:
            context.warnings.append("Search results may contain low-credibility sources")

        output = SkillOutput(
            content=results,
            output_type="search_results",
            metadata={
                'query': query,
                'num_results': len(results),
                'avg_credibility': context.avg_credibility,
            }
        )

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            output=output,
            warnings=context.warnings,
        )

    def _perform_search(self, query: str) -> List[Dict]:
        """Perform search (simulated)"""
        # In real implementation, would call actual search API
        return [
            {'title': f'Result for: {query}', 'url': 'https://example.com', 'snippet': '...'}
        ]


class SkillRegistry:
    """Registry of available skills"""

    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base
        self.skills: Dict[str, BaseSkill] = {}

        # Register default skills
        self._register_default_skills()

    def _register_default_skills(self):
        """Register built-in skills"""
        self.register(EmailWriterSkill(self.knowledge_base))
        self.register(CalendarManagerSkill(self.knowledge_base))
        self.register(WebSearcherSkill(self.knowledge_base))

    def register(self, skill: BaseSkill):
        """Register a skill"""
        self.skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def get(self, name: str) -> Optional[BaseSkill]:
        """Get a skill by name"""
        return self.skills.get(name)

    def get_for_task(self, task: str) -> Optional[BaseSkill]:
        """Get the best skill for a task"""
        task_lower = task.lower()

        # Simple keyword matching (in real implementation, would use NLP)
        if any(kw in task_lower for kw in ['email', 'write', 'compose', 'draft']):
            return self.skills.get('email_writer')
        elif any(kw in task_lower for kw in ['schedule', 'meeting', 'calendar', 'book']):
            return self.skills.get('calendar_manager')
        elif any(kw in task_lower for kw in ['search', 'find', 'research', 'look up']):
            return self.skills.get('web_searcher')

        return None

    def list_skills(self) -> List[str]:
        """List all registered skills"""
        return list(self.skills.keys())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test the new skill system
    from knowledge import KnowledgeBase, RuleGenerator

    kb = KnowledgeBase(Path("./data/learning"))
    generator = RuleGenerator()

    # Add a timezone rule
    rule = generator.generate_rule_from_error("TimezoneError", frequency=5, confidence=0.75)
    if rule:
        kb.add_rule("email_writer", rule)

    # Create skill registry
    registry = SkillRegistry(kb)

    # Create execution context
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
