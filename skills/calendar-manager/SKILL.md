---
name: calendar-manager
description: >-
  Manages calendar operations and scheduling. Handles conflict detection,
  participant preference checking, and timezone conversion.
license: MIT
compatibility: Python 3.8+
metadata:
  author: skillforge
  version: "1.0"
  category: productivity
  output_type: calendar_event
  triggers:
    - calendar
    - schedule
    - meeting
    - book
    - reserve
  tools:
    - calendar_availability
    - calendar_schedule
  context_fields:
    has_conflict: { type: bool, default: false }
    violates_preferences: { type: bool, default: false }
---

# Calendar Manager

## Capabilities
- Meeting scheduling
- Time slot availability checking
- Timezone conversion
- Conflict detection
- Participant preference tracking

## Usage
Provide a task description mentioning scheduling or calendar operations.
The skill parses meeting details, applies learned rules, and creates events.

## Examples
- "Schedule a team sync for tomorrow at 10 AM"
- "Book a 1-on-1 meeting with Sarah"
- "Reserve a 2-hour retrospective for Friday"
