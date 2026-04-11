# Integration Semantics

- "Tracker" means the bounded list state accessed through `add_item`, `update_item`, and `read_list`.
- `todo.txt` is a separate file artifact and is not the same as the live tracker.
- `handoff.md`, `rollout.md`, `status.txt`, `status.md`, and `daily_log.txt` are artifact files.
- When the user asks what is currently in an artifact, current file state is authoritative.
- When the user asks for tracker contents and tools are allowed, `read_list` is authoritative.
- When a tracker item wording changes, prefer `update_item` instead of add/remove churn.
- "Current config" means the live contents of `config.json`, not earlier recalled values.
- "Original config" means the baseline value before later explicit changes.
- If the user says an older note is stale and a newer one is current, prefer the newer explicit note.
- If a turn mixes stale and current facts, grounded verification tools should win over recalled guesses.
- If a user says "don't change anything", inspection-only behavior is expected.
- If a user says "without using any tools", memory-only behavior is expected.
- If a user asks for a checkpoint or wrap-up, concise bullets are preferred.
