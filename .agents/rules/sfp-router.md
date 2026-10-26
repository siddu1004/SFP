# SFP Hive Local Router Preference

For any local LLM operations, code drafting, local code reviews, offloading, or repo-to-skill conversions:
- **Router Endpoint**: `http://127.0.0.1:8787/v1`
- **Default Model**: `auto` (or `sfp/light`, `sfp/normal`, `sfp/heavy` based on task size)
- The SFP router at `http://127.0.0.1:8787/v1` manages model selection, health, cooldowns, and failover across local runtimes (LM Studio, Ollama) and configured cloud providers.
