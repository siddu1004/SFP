---
name: freellmapi
description: Run and use FreeLLMAPI, one OpenAI-compatible /v1 endpoint that stacks the free tiers of 34 LLM providers with automatic routing and failover. Use when the user wants free LLM inference, to point an OpenAI SDK, coding agent or other client at a free multi-provider endpoint, to self-host FreeLLMAPI with Docker, to pick a routing strategy such as auto:fast or auto:smart, or to fix a FreeLLMAPI setup problem.
---

> **This skill needs FreeLLMAPI, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.

# FreeLLMAPI

[FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) aggregates the free tiers of many LLM providers behind one OpenAI-compatible `/v1` API. Provider keys are stored encrypted, and a router picks an available model and fails over when one is rate-limited.

The docs are bundled in `reference/`:

- `reference/install.md`: Docker, Docker Compose, local development, LAN access, backups
- `reference/rest-api.md`: endpoints, routing strategies, streaming, tools, vision, embeddings, the Anthropic Messages surface
- `reference/clients.md`: coding agents and other clients, the config generator, the MCP server
- `reference/troubleshooting.md`: common problems

Read the one that matches the task instead of all four.

## Run it

With Docker installed, the project's one-liner sets up `~/freellmapi`, generates an encryption key, pulls the image and starts the container (safe to re-run; it keeps your `.env`):

```bash
curl -fsSL https://freellmapi.co/install.sh | bash
```

Tell the user they can read the script first at that URL before piping it to bash. On Windows there is a desktop installer on the project's GitHub Releases page. Then:

1. Open http://localhost:3001.
2. Add provider keys on the **Keys** page, and reorder the **Fallback Chain** if wanted.
3. Copy the unified API key from the **Keys** page header. Clients use that key, never the provider keys.

## Use it

Point any OpenAI-compatible client at `http://localhost:3001/v1` with the unified key:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:3001/v1", api_key="freellmapi-your-unified-key")
resp = client.chat.completions.create(
    model="auto",  # or "auto:fast", "auto:smart", "auto:cheap", "auto:reliable", "auto:balanced", or a model id
    messages=[{"role": "user", "content": "Hello"}],
)
```

- `model: "auto"` lets the router pick. `auto:fast` favors speed, `auto:smart` favors the strongest models, `auto:reliable` favors recent success rate, `auto:balanced` is the default blend.
- The response header `x-routed-via` says which provider answered.
- For a coding agent, use the project's generator described in `reference/clients.md` rather than hand-editing the agent's config.

## Rules

- Keys go in the dashboard or environment, never in committed files.
- Free tiers have quotas and providers change them without notice. If requests fail, check the dashboard's logs and fallback chain before changing code.
- The project has paid options (a live model catalog). Mention them only if asked; the free install works without them.
- Verify commands against `reference/install.md`, since install steps change between releases.
