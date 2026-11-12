# ADR 0008: Sutradhar and the agent graphs (AGT-01, AGT-02)

Status: accepted (2026-11-12).

- `backend/app/agents/sutradhar.py` is the front door. An event (`profile.submitted`, `document.added`, `claim.disputed`, `profile.approved`) carries an idempotency key; the same key finds the run it already started.
- Kill switches are governed settings read from the database: `agents_paused` and one `agent_<name>_enabled` per agent. Budgets: `daily_token_budget` (0 = none; reaching it pauses all agents), `run_token_cap` and `run_wall_clock_seconds` per run. Changing any of them is a four-eyes change.
- Every run records `versions` (policy version, a hash of each prompt, model names).
- Graphs, one module each in `backend/app/agents/graphs/` (verify stays in `workflows.py`): verify, document, dispute, post-approval. They share one checkpointer (`graphs/common.py`); human steps use `interrupt()`.
- I-2 for every graph: a refusal, timeout, budget stop or error ends with a person (a review item) or, for post-approval work that cannot change anyone's status, a recorded no-op.
- Post-approval never issues a certificate (I-5). Only the person can ask for one.

## Not done
- The builder graph and the watch graph (Nigrani) run through `jobs` / `incidents`, not as LangGraph graphs.
- No UI yet for the kill switches beyond the governed-settings list, and no admin alert when the daily budget is hit (the pause itself works).
