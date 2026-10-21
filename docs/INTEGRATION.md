# Full Integration Guide

This guide takes you from nothing to a fully set up IDE: SFP's skills and router, the SFP MCP server, the full ECC toolkit and an OmniRoute gateway. Every step has the exact commands. Do the parts you want, in order.

## What each piece does

| Piece | What it gives you | Where it comes from |
|---|---|---|
| SFP skills and router | 560 skills sorted into categories, plus `sfp`, which finds the right one | This repo |
| SFP MCP server | Search and read every skill from any MCP client, with nothing copied | This repo (`mcp/sfp_mcp.py`) |
| ECC (Everything Claude Code) | SFP carries ECC's **skills**. ECC itself also has 71 agents, hooks, commands and rules, which skills folders cannot carry | [affaan-m/ECC](https://github.com/affaan-m/ECC) |
| OmniRoute | SFP carries the 45 `ai-gateway` **skills** that drive it. The gateway server is a separate program that routes your IDE to 375 providers through one endpoint | [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute) |

The point to keep in mind: SFP gives your agent the knowledge of ECC and OmniRoute. To get ECC's agents and hooks, or a running gateway, you install those projects too. The steps below do that without the installs fighting each other.

**Shortcut for the programs:** each skill that guides OmniRoute, Strix, claude-mem, FreeLLMAPI or Agent Reach carries its own setup (`python3 scripts/sfp_app.py status`, `install`, `start`). From the SFP checkout, `python3 scripts/install.py apps list` shows them all and `apps install omniroute` shows the plan; add `--yes` to run it. The manual steps below are the same commands, with more choices.

## Step 0: Check your tools

```bash
git --version
python3 --version      # SFP installer and MCP server
node --version         # ECC and OmniRoute need Node.js 18 or newer
claude --version       # only if you use Claude Code (ECC needs 2.1 or newer)
```

Install anything missing first. Windows users run these in PowerShell.

## Step 1: Install SFP

macOS and Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1 | iex
```

This installs the `starter` preset into every IDE it finds. To choose, add arguments (macOS and Linux shown):

```bash
# One IDE, one preset
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --tools cursor --profile frontend-dev

# Exact categories, several IDEs
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- --tools cursor,codex,gemini --categories backend,security,devops
```

Check what was found and what is available:

```bash
~/.sfp/SFP/install.sh list
```

**Claude Code users** can use plugins instead of folders:

```text
/plugin marketplace add siddu1004/SFP
/plugin install sfp@sfp
/plugin install frontend@sfp
/plugin install backend@sfp
```

Replace `frontend` and `backend` with any category from `install.sh list`.

## Step 2: Add the SFP MCP server

This lets every MCP-capable IDE search and read all skills without installing them.

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh -s -- mcp
```

Windows:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/siddu1004/SFP/main/get.ps1))) mcp
```

Limit it to some IDEs with `--tools cursor,claude`. Undo it with `--remove`.

## Step 3: Add ECC

Choose the ECC path for each IDE. **Use one install method per IDE.** ECC's own docs warn that stacking methods duplicates skills, commands and hooks.

### Claude Code

Guided setup, which ECC recommends (needs Node.js 18+, Git and Claude Code 2.1+):

```bash
npx ecc-universal@2.2.3 setup
```

Choose **Global user** and **Standard** hooks for a typical personal setup. Start a new Claude Code session and run `/plugin list` to confirm `ecc@ecc` is enabled.

Or the native plugin commands, inside Claude Code:

```text
/plugin marketplace add https://github.com/affaan-m/ECC
/plugin install ecc@ecc
```

Pick one of the two, not both. ECC's plugin cannot ship `rules`, so add the rule packs you want by hand:

```bash
git clone https://github.com/affaan-m/ECC.git
cd ECC
mkdir -p ~/.claude/rules/ecc
cp -R rules/common ~/.claude/rules/ecc/
cp -R rules/typescript ~/.claude/rules/ecc/    # replace with your stack
```

### Codex

```bash
codex plugin marketplace add affaan-m/ECC
codex plugin add ecc@ecc
codex plugin list --json
```

Run Codex once first, so its config exists. Codex asks you to trust ECC's hooks.

### Claude Code, Codex and Kimi Code in one pass

```bash
npx ecc-universal@2.2.3 install --guided
```

It shows each destination and asks for one confirmation. For a scripted run:

```bash
npx ecc-universal@2.2.3 install --guided \
  --harness claude --harness codex --harness kimi \
  --claude-scope local --claude-hooks standard \
  --profile core --yes
```

Preview without writing anything by adding `--dry-run`.

### Cursor, Gemini, OpenCode, Antigravity and others

ECC has managed adapters for `cursor`, `antigravity`, `gemini`, `opencode`, `codebuddy`, `joycode`, `qwen`, `zed`, `hermes` and `openclaw`. They are capability-limited compared with Claude Code. Example:

```bash
npx ecc-universal@2.2.3 install --profile minimal --target cursor
npx ecc-universal@2.2.3 doctor --target cursor
```

Read ECC's [platform support matrix](https://github.com/affaan-m/ECC#platform-support) before expecting every feature in a given IDE.

### Avoiding duplicate ECC skills

SFP carries about 300 of ECC's skills inside its categories (`agents`, `agent-dev`, `testing-quality`, `backend`, `frontend` and others). If you also install ECC as a plugin, you will see some skills twice. Pick one:

- **ECC is your main toolkit.** Install ECC as above, and install only `sfp` from SFP (the router, about 159 tokens), plus categories that are not from ECC, such as `security`, `data-apis` or `design-styles`:

  ```bash
  ~/.sfp/SFP/install.sh --categories sfp,security,data-apis,design-styles
  ```

  The router still finds every other skill on demand through `~/.sfp/root`.
- **SFP is your main source.** Skip the ECC plugin. You get ECC's skills, but not its agents, hooks, commands or rules.

If you already have duplicates, remove the SFP side with `~/.sfp/SFP/install.sh uninstall --tools <ide>`, or follow ECC's "Reset / Uninstall ECC" section.

## Step 4: Add OmniRoute

OmniRoute is a local gateway. Your IDE talks to one endpoint, `http://localhost:20128/v1`, and OmniRoute routes to the providers you connect, with fallbacks.

### 4a. Install and start the server

```bash
npm install -g omniroute
omniroute
```

Dashboard: `http://localhost:20128`. API: `http://localhost:20128/v1`.

With npm 11 or later, global installs can block the scripts OmniRoute needs. Allow the packages npm names in its warning, for example:

```bash
npm install -g --allow-scripts=omniroute,keytar,onnxruntime-node,@parcel/watcher,@swc/core,protobufjs,esbuild omniroute
```

Use the package list from your own npm warning if it differs.

Docker instead of npm:

```bash
docker run -d --name omniroute --restart unless-stopped --stop-timeout 40 \
  -p 127.0.0.1:20128:20128 -v omniroute-data:/app/data diegosouzapw/omniroute:latest
```

For a coding agent through Docker, raise the memory limit, as OmniRoute's docs advise:

```bash
docker run -d --name omniroute --restart unless-stopped --stop-timeout 40 \
  -e OMNIROUTE_MEMORY_MB=8192 --memory=10g \
  -p 127.0.0.1:20128:20128 -v omniroute-data:/app/data diegosouzapw/omniroute:latest
```

### 4b. Connect a provider

Open the dashboard, go to **Providers**, pick a provider whose terms and quota fit you, and add its API key or finish its account sign-in. Free tiers can need signup or a payment method. You are responsible for following each provider's terms. Run the guided wizard if you prefer the terminal:

```bash
omniroute setup
omniroute doctor      # checks providers, ports and native dependencies
```

Copy an API key from **Dashboard, then Endpoints**, and check it works:

```bash
curl http://localhost:20128/v1/models -H "Authorization: Bearer YOUR_KEY"
```

### 4c. Point your IDE at it

For most tools the settings are the same:

```text
Base URL: http://localhost:20128/v1
API Key:  the key from Dashboard, then Endpoints
Model:    auto
```

For the tools OmniRoute knows, it can write the config for you. Add `--dry-run` first to preview:

```bash
omniroute setup-claude        # Claude Code profiles in ~/.claude/profiles/
omniroute setup-codex
omniroute setup-opencode
omniroute setup-cursor
omniroute setup-cline
omniroute setup-continue
omniroute setup-zed
omniroute setup-aider
omniroute setup-goose
omniroute setup-qwen
```

Or launch a CLI through OmniRoute without writing any config:

```bash
omniroute run claude --model openai/gpt-5.4
omniroute run codex  --model glm/glm-5.2
```

Claude Code reads its gateway from environment variables (it has no base-URL flag). `omniroute launch` sets them for you. By hand:

```bash
export ANTHROPIC_BASE_URL=http://localhost:20128      # no /v1 on the end
export ANTHROPIC_AUTH_TOKEN=YOUR_KEY
claude
```

Restart Claude Code after changing these variables.

Some IDEs cannot be pointed at a custom endpoint, or only partly. OmniRoute's own tool table lists Cursor, Antigravity, Kiro and Hermes as having no native base-URL support, and Windsurf as limited. For those, read OmniRoute's [CLI Tools guide](https://github.com/diegosouzapw/OmniRoute/blob/main/docs/reference/CLI-TOOLS.md) for the supported route, such as its VS Code extension or its dashboard recipes.

### 4d. Give your agent OmniRoute's own tools over MCP

```bash
claude mcp add-server omniroute --type http --url http://localhost:20128/api/mcp/stream
```

For other MCP clients, run `omniroute --mcp` as a stdio server. OmniRoute documents 110 MCP tools behind this endpoint.

### 4e. Install the SFP skills that teach your agent to drive it

```bash
~/.sfp/SFP/install.sh --categories ai-gateway
```

You then ask in plain language, for example: "Use the OmniRoute skills to add a fallback route for my coding model."

## Step 5: Check everything works

| Check | Command or prompt | You should see |
|---|---|---|
| SFP skills installed | `~/.sfp/SFP/install.sh list` | Your tools marked as found |
| Router works | "Use sfp to find a skill for reviewing my UI for accessibility." | It names `accessibility-audit` or similar and follows it |
| SFP MCP works | "Search SFP for a skill about postgres migrations." | A result from `search_skills` |
| ECC (Claude Code) | `/plugin list` | `ecc@ecc` enabled |
| ECC (other targets) | `npx ecc-universal@2.2.3 doctor --target cursor` | A clean report |
| OmniRoute server | `curl http://localhost:20128/v1/models -H "Authorization: Bearer YOUR_KEY"` | Your connected models |
| OmniRoute through the IDE | Ask any question | A reply, and a request in the OmniRoute dashboard |

## Step 6: Update, and take it all back out

Update:

```bash
curl -fsSL https://raw.githubusercontent.com/siddu1004/SFP/main/get.sh | sh   # SFP
npx ecc-universal@2.2.3 setup                                                 # ECC for Claude Code
npm update -g omniroute                                                       # OmniRoute
```

Remove:

```bash
~/.sfp/SFP/install.sh uninstall --tools cursor          # SFP skills, per IDE
~/.sfp/SFP/install.sh mcp --remove                      # SFP MCP server
npm uninstall -g omniroute                              # OmniRoute
docker rm -f omniroute                                  # if you used Docker
```

In Claude Code, remove plugins with `/plugin uninstall <name>@<marketplace>`, for example `ecc@ecc` or `frontend@sfp`. For ECC outside Claude Code, use ECC's "Reset / Uninstall ECC" section.

## Recommended setups

| You want | Do this |
|---|---|
| The lightest useful setup | Step 1 with `--categories sfp`, then Step 2 |
| Everything, Claude Code | Steps 1, 2, 3 (Claude Code), 4 and 5; install only `sfp` plus non-ECC categories from SFP |
| Everything, Cursor or Gemini | Steps 1 to 5 with the ECC adapter for that IDE; OmniRoute through its supported route |
| Free or cheap models in your IDE | Step 4, then `omniroute setup-<your-tool>` |
| Team machines | Pin ECC with `ecc-universal@<version>`, pin OmniRoute with a Docker tag such as `:X.Y.Z`, and commit the SFP commit from `sources.lock.json` |

## What I tested, and what I did not

- **Tested:** the SFP installer and MCP registration, including with Claude Code.
- **Not run:** ECC's installer, OmniRoute's server and the tool-specific setup commands. The commands here are taken from each project's own documentation as of the versions in SFP's last sync (ECC 2.2.3 docs, OmniRoute 3.8.53). Their flags and versions change, so if a command differs from what the project's README says today, trust the project's README.
- **Third-party software:** ECC and OmniRoute are separate projects with their own licenses, updates and security models. OmniRoute holds your provider credentials, so keep it bound to `127.0.0.1` unless you know why you need otherwise.
