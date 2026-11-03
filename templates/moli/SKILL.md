---
name: moli
description: "Fast, resource-light headless browser automation using Moli for web scraping and AI agent DOM extraction. Use when running lightweight browser automation, extracting clean DOM content, or scraping web data without heavy Chromium overhead."
---

# Moli Headless Browser

High-performance, resource-efficient headless browser built in Rust specifically for AI agents (`lexmount/moli`). Moli renders DOM, executes JavaScript, and returns clean, structured content with a fraction of Chromium's RAM footprint.

## Use This Skill When

- Scraping dynamic JavaScript web pages where simple HTTP clients fail.
- Extracting semantic DOM structures and text for LLM consumption without multi-gigabyte browser dependencies.
- Running parallel web verification or link checking in constrained environments.

## Commands & Usage

```bash
# Launch Moli headless session
moli --url "https://example.com" --extract "article"

# Export structured JSON snapshot
moli dump-dom --url "https://news.ycombinator.com" --output /tmp/dom.json
```

## Checks & Verification

- [ ] Confirm JavaScript execution finishes before DOM snapshot is captured.
- [ ] Verify extracted content retains semantic headings (`h1`-`h6`) and link references.

## Sources

- [Moli GitHub Repository](https://github.com/lexmount/moli)
