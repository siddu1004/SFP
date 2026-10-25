# The router: use your local models, and never stop at a limit

`mcp/sfp_route.py` is a small local model router, standard library only. It speaks the OpenAI chat API, so any tool that lets you set a base URL (`http://127.0.0.1:8787/v1`, any key, model `auto`) can use it. OmniRoute does more and needs Node 22, a database and a lot of setup; this does the part you asked for with nothing to install.

```
python3 mcp/sfp_route.py discover        # finds Ollama, LM Studio, llama.cpp, Jan, vLLM on this machine
python3 mcp/sfp_route.py setup --yes     # writes ~/.sfp/routes.json from those and from the keys you have set
python3 mcp/sfp_route.py serve           # runs it on 127.0.0.1:8787
python3 mcp/sfp_route.py plan "refactor the billing service"   # which model would be tried, in what order
python3 mcp/sfp_route.py status          # ready, cooling down and why, requests served
```

## How it decides

1. **Size the request.** `light` (a short question, a rename), `normal`, or `heavy` (tools with a long context, or words like architecture, refactor, security audit). The text is counted, never stored.
2. **Filter.** A model is a candidate if it has room for the request (`ctx`), takes tools when the request uses them, and its key (if it needs one) is set.
3. **Order.** Policy `local-first` (default): local before cloud, and the weakest model that is strong enough (strength 1 to 3, guessed from the name: `7b` is 1, `14b` is 2, `70b` is 3). Models that are too weak come last, as a last resort. `cheap-first` and `strong-first` are the other policies. Ask for a size with the model name `sfp/light`, `sfp/normal` or `sfp/heavy`, or name one model.
4. **Fail over.** On 429, 5xx, 401/402/403, a timeout or an unreachable server the model cools down (Retry-After honoured, else 30 s doubling to 10 min) and the next one answers, before any byte has gone to your tool. A stream already started cannot be moved. If every model fails you get a 503 that says why for each.

## Local models are found while it runs

While `serve` is running it looks for local models again every 30 seconds (`--rediscover N`, 0 to turn it off). A runtime you start later joins with its models and their strengths, new models on a running runtime are added, and a local runtime that stops answering is switched off and switched back on when it returns. Cloud providers are never touched.

## What it is not (yet)

- It routes `/v1/chat/completions` only. Tools that speak the Anthropic API (Claude Code itself) cannot use it; it works for OpenAI-compatible clients such as Cline, Continue, Codex, Cursor's custom endpoint, Aider and your own scripts. The IDE's own built-in agent model (Antigravity's "Gemini 3.8 Flash") is chosen by the IDE, not by SFP, and cannot be re-routed from outside.
- It does not translate between formats and does not count real tokens: size is characters divided by four.
- Cooldowns are kept in memory and reset when it restarts. Nothing is written but `routes.json` (names of key variables, never keys) and `route_usage.jsonl` (provider, model, size, ok, milliseconds; never text).
- Tested against fake servers, not against a real Ollama or a real provider (the sandbox blocks both). The first run on your machine is the real test; `discover` and `plan` show what it sees before anything is routed.

## Prompt for Antigravity: the router in the sidebar

> On `feat/chat-extension`, merge `origin/main`, then build the router's interface in `extensions/antigravity-hive/`. Use `python3 mcp/sfp_route.py` through `src/hive.ts` (add `routeArgs` and parsers; no editor code in `hive.ts`), public VS Code API only, no new runtime dependencies, every dynamic string escaped, tests for everything.
> 1. A **Models** section in the SFP Hive sidebar (a collapsible view `sfpHive.models`). It runs `discover` and lists local runtimes and their models with a strength chip (1 to 3, editable), and cloud providers whose key variable is set (show the variable name, never a value).
> 2. A **Set up** button: runs `setup` (no `--yes`) and shows the config it would write, then **Write it** runs `setup --yes`. A policy picker (local-first, cheap-first, strong-first).
> 3. A **Start router** / **Stop** toggle. It starts `serve` as a child process owned by the extension (not a shell), shows the base URL with a Copy button and the line "set your tool's base URL to this, key anything, model auto", and stops it when the extension deactivates.
> 4. A live **status** list from `GET /health` every 5 s while it runs: each model ready or cooling down with the reason and seconds left, ok and failed counts, and a "last used" mark. A model that has failed twice shows a warning.
> 5. A **Try it** box: type a prompt, press Plan, and show `plan` output (the tier and the order). Another button sends a real one-line request through the router and shows the answer and which model gave it (`X-SFP-Model`).
> 6. When `needs --check` reports `never-run-out` with `router.running == false`, show a card in Choose: "Keep working when a model runs out" with the one `action` as a button that opens the Models section. If routes.json is missing, the button runs Set up.
> 7. Commands `sfpHive.routerStart`, `sfpHive.routerStop`, `sfpHive.routerSetup`, `sfpHive.focusModels`; update the manifest and `tests/test_extension.py`.
> Acceptance: R1 with no local server, Set up says nothing was found and what to do. R2 with a local Ollama, its models appear with strengths. R3 Start shows the URL; `curl` to `/v1/models` works. R4 stop the local server and send a request: the cloud model answers and the status shows the local one cooling down. R5 no key value appears anywhere in the UI, logs or `routes.json`. R6 works at a sidebar width of 260 px, in light and dark themes, by keyboard only.
> Commit and push after each numbered group and stop with a short report listing R1 to R6 as pass or fail with one line of evidence.
