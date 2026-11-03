---
name: browser-use
description: "Automate browser interactions for AI agents using the Browser-Use Python library and Playwright. Use when building web scraping agents, automating complex UI workflows, interacting with authenticated web apps, or testing browser tasks."
---

> **This skill needs Browser-Use, which is installed separately.** From this skill's folder, run `python3 scripts/sfp_app.py status` to see whether it is installed and running. If it is not, run `python3 scripts/sfp_app.py install` to get the plan (it changes nothing), tell the user what it will do, and run it again with `--yes` only after they agree. `start` runs it when it is installed but stopped.

# Browser-Use Web Automation

Automate browser interactions for AI agents using `browser-use`. Browser-Use connects language models directly to headless Chromium via Playwright, converting raw web pages into structured visual and DOM representations that agents can click, type, navigate, and extract data from.

## Use This Skill When

- Building autonomous agents that must navigate dynamic websites, submit forms, or click buttons.
- Extracting data from modern SPAs where simple HTTP scraping fails.
- Automating end-to-end browser workflows with agent supervision.

## Installation & Setup

```bash
pip install browser-use playwright
playwright install chromium
```

## Basic Agent Workflow

```python
import asyncio
from langchain_openai import ChatOpenAI
from browser_use import Agent

async def main():
    agent = Agent(
        task="Navigate to example.com, search for 'documentation', and return the top headline.",
        llm=ChatOpenAI(model="gpt-4o"),
    )
    history = await agent.run()
    print(history.final_result())

if __name__ == "__main__":
    asyncio.run(main())
```

## Verification Checklist

- [ ] Chromium binaries are installed (`playwright install chromium`).
- [ ] Agent interactions handle cookies, consent modals, and dynamic hydration delays.
- [ ] Sensitive session tokens or credentials are kept in environment variables.

## Pitfalls

- **Bot Detection**: Rapid automated actions may trigger Cloudflare or CAPTCHA challenges; use realistic delays or headful browser debugging when diagnosing blocks.
- **Context Limits**: Full DOM tree dumps can overwhelm LLM contexts; Browser-Use automatically trims irrelevant nodes, but narrow the task prompt to specific page regions.

## Sources

- [Browser-Use Documentation](https://docs.browser-use.com/)
- [Browser-Use GitHub Repository](https://github.com/browser-use/browser-use)
