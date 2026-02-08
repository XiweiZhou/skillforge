---
name: web-searcher
description: >-
  Performs web searches and retrieves information. Handles query optimization,
  source credibility assessment, and result ranking.
license: MIT
compatibility: Python 3.8+
metadata:
  author: skillforge
  version: "1.0"
  category: research
  output_type: search_results
  triggers:
    - search
    - find
    - research
    - look up
    - query
  context_fields:
    avg_credibility: { type: float, default: 0.5 }
---

# Web Searcher

## Capabilities
- Web search execution
- Query refinement
- Source filtering and credibility assessment
- Result ranking
- Citation gathering

## Usage
Provide a task description mentioning search or research.
The skill optimizes queries, applies learned rules, and returns results.

## Examples
- "Search for Python best practices 2024"
- "Find documentation on React hooks"
- "Research machine learning frameworks comparison"
