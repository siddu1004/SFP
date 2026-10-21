# Changelog

## 3.0.0

- **The selector learns from feedback.** After a task, report which chosen skills `helped`, were `unhelpful`, were `ignored` or were `missing` (`give_feedback`, or `sfp_select.py feedback`). A small model of which task words go with which skills adjusts later choices, can find a skill that keyword search missed, and fades old reports. A reported mistake is fixed on the same kind of task 94% of the time. On tasks it has not seen, accuracy moved from 86.8% to 87.7%, which is within noise. `status` shows what was learned and `forget` deletes it. See `docs/SELECTION.md`.
- **Renamed.** The skill `sfp-manager` is now `sfp-select`, the engine `mcp/sfp_hive.py` is `mcp/sfp_select.py`, and the MCP tool `recommend_stack` is `select_skills`. `record_usage` is replaced by `give_feedback`, and `learning_status` is new. The installer removes a leftover `sfp-manager` folder that it created. The earlier engine stays available as `--engine v1`.
- The documentation and the README describe the algorithm in plain engineering terms. The insect-colony models it draws on are credited in `docs/SELECTION.md`. `docs/HIVE.md` became `docs/SELECTION.md`, and `docs/MANAGER.md` became `docs/PRODUCT.md`.
- The first learning design, a weight per skill, technology and signal, made unseen tasks worse and was dropped. The history is in `docs/SELECTION.md`.
- With no feedback, selection is byte-for-byte what 2.0.1 produced on all 137 evaluation tasks.
- New tests: `tests/test_learn.py` (storage and privacy, feedback validation, the model, the loop over MCP and the command line, and the learning curve) and `tests/test_select.py`.
- The README is rebuilt around selection and learning.

## 2.0.1

- **Faster, with identical answers.** Search about 5x faster, next-skill prediction about 15x, a whole decision about 3x, calls through the running MCP server 3 to 5x, and the first call after start-up about 7x. A one-shot command line call is about 25% faster. Answers were compared byte for byte on all 137 evaluation tasks before and after. See `docs/SELECTION.md#speed`.
- The sync now writes `index.json`, a saved search index that start-up loads if it matches the catalog and tokenizer exactly, and rebuilds otherwise.
- The MCP server loads the hive in the background after start-up.
- `tests/test_speed.py` pins each fast path to the plain definition it replaced, and holds speed budgets.

## 2.0.0

- **The hive.** `sfp-manager` now chooses skills with a colony algorithm modelled on how honeybees divide work (`mcp/sfp_hive.py`): independent scouts and a quorum rule, stop signals between rival skills, response thresholds that decide how many skills each job takes, thresholds that learn from recorded outcomes, and pheromone trails that evaporate with a 30-day half-life. On 22 new tasks written before it existed, it put the right skill in the stack 86% of the time, against 68% for v1 and 14% for plain search. See `docs/HIVE.md`.
- `recommend_stack` and `predict_next` in the MCP server use the hive. `--engine v1` keeps the previous engine available.
- The `sfp-manager` skill tells the agent to ask once per phase of work, and lists the colony rules in plain words for when Python is not available.
- New held-out task set `tests/hive_fresh.json` and tests `tests/test_hive.py`.
- Fixed: v1 could recommend `sfp-manager` itself.
- The README is rebuilt around the hive, with figures regenerated from the evaluation on every sync.

## 1.x

- `sfp-manager` and the v1 stack engine, the MCP server, the installer for 16 IDEs, the ECC and OmniRoute integration guide, search ranking and the generated README.
