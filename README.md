# 🧠 GenState Management

> **[Architectural Pattern Extracted from Production]**
> *Core state reconciliation logic extracted from a production interactive-fiction platform. Demonstrates a lightweight pattern for maintaining world-state consistency across LLM sessions using targeted entity extraction. This is an architectural reference pattern, not a standalone library. It assumes you will wire it into your own generalized entity classifier to handle complex contradictions.*

A Python framework for maintaining consistent world-state in non-deterministic LLM systems. This engine provides a structured persistence layer for keeping agentic AI (GPT-4, Claude) data synchronized across long-running sessions.

- 🛠️ **State Persistence**: Handles structured tracking of world objects and history.
- 🔄 **Consistency Layer**: Logic to reconciliation speculative hallucinations with the source of truth.
- 📦 **Model Agnostic**: Works as a standalone engine for any LLM-driven storytelling or simulation project.

### Usage
```python
from genstate.engine import StateDirector
director = StateDirector(config="world_config.json")
director.update_state(new_events)
```

**Implementation Details**:
- Developed to solve state-drift issues in recursive storytelling agents.
- Uses a deterministic update-loop to verify AI outputs against current constraints.
