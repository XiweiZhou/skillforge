---
name: email-writer
description: >-
  Writes professional emails based on user intent. Handles spam detection,
  timezone awareness, and attachment management.
license: MIT
compatibility: Python 3.8+
metadata:
  author: skillforge
  version: "1.0"
  category: communication
  output_type: email
  triggers:
    - email
    - write email
    - compose
    - draft email
  tools:
    - web_search
  context_fields:
    has_timezone: { type: bool, default: false }
    has_attachment: { type: bool, default: false }
---

# Email Writer

## Capabilities
- Professional tone generation
- Subject line creation
- Timezone-aware scheduling references
- Spam trigger avoidance
- Attachment reference handling

## Usage
Provide a task description mentioning email composition.
The skill parses intent, applies learned rules, and generates output.

## Examples
- "Write an email about the meeting at 2 PM tomorrow"
- "Draft a follow-up email to the client"
- "Compose an introduction email for the new team member"
