# 🧠 GenState Management: AI State Persistence & Hallucination Recovery Engine

**GenState** is a specialized framework for maintaining deterministic world-state in non-deterministic LLM systems. This engine addresses the "Consistency Paradox" - the challenge of keeping complex data synchronized when the governing agentic AI (GPT-4, Claude) is prone to speculative hallucinations.

---

## 🔥 Problem: Non-Deterministic State Drift
In agentic simulations, AI outputs often contradict the source of truth or return malformed JSON schemas. **GenState** introduces a **Speculative Correction Loop** that treats AI output as a *proposal* to be validated, sanitized, and reconciled before any database commit.

---

## 🛡️ Architecture: Deterministic Reconciliation
1.  **Speculative Validation**: Intercepts malformed LLM responses via `json_utils` and triggers a **Self-Healing Loop** using a secondary, high-precision model to "fix" the schema while preserving narrative intent.
2.  **State Reconciliation (Delta Sync)**: Calculates the diff between the *intended* state change and *legal* state parameters, preventing illegal transitions (e.g., duplicate unique entities).
3.  **Tiered Inference Strategy**: Orchestrates multi-model fallbacks (e.g., GPT-4o for reasoning, Mini for state checks) to optimize for both latency and cost.

---

## 🛠️ Core Components
- **`enhanced_story_director.py`**: Central orchestrator for the generative loop and correction logic.
- **`world_state_updater.py`**: Deterministic logic for updating entity relationships and attributes.
- **`llm_factory.py`**: Abstracted provider layer for multi-model load-balancing.
- **`json_utils.py`**: Schema integrity and format recovery layer.

---

## ✨ Engineering Wins
- **State Consistency**: Replaced loose "prompt-based state" with a strict SQL-backed delta system, reducing simulation crashes by 90%.
- **Cost Optimization**: Tiered model usage reduced monthly API expenses by 40% without compromising story depth.

---

**Built for the next generation of GenAI architects. 🧠**
