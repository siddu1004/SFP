---
name: searxng
description: "Configure and query a private SearXNG metasearch instance to retrieve web search results without commercial tracking. Use when conducting private web research, aggregating search engines, or bypassing web search rate limits."
---

# SearXNG Metasearch

Query and configure a private, self-hosted SearXNG metasearch instance for agent web research. SearXNG aggregates search results from over 70 search engines (Google, Bing, DuckDuckGo, Wikipedia, ArXiv) while protecting agent privacy and eliminating query rate limits.

## Use this skill when
- Searching the public web without third-party tracking, profiling, or search API paywalls.
- Aggregating multi-source search results across academic, code, and web categories.
- Self-hosting an internal search proxy for offline or air-gapped development environments.

## Steps
1. **Start the SearXNG container**:
   Ensure Docker is running and launch the container with local port binding:
   ```bash
   docker run -d -p 8080:8080 -v ./searxng:/etc/searxng:rw --name searxng searxng/searxng
   ```
2. **Verify instance health**:
   Confirm the instance is responding to HTTP queries:
   ```bash
   curl -s "http://127.0.0.1:8080/healthz"
   ```
3. **Execute search queries via JSON API**:
   Query SearXNG using JSON format output:
   ```bash
   curl -s "http://127.0.0.1:8080/search?q=astropy+fits+tables"
   ```
4. **Parse structured results**:
   Extract title, URL, and snippet text from the `results` array in the JSON response.

## Checks
- Check that the SearXNG container is active and listening on port 8080.
- Verify JSON output contains non-empty results.
- Check engine response times in the `unresponsive_engines` JSON property.

## Pitfalls
- Public SearXNG instances may enable bot protections; prefer running a local Docker instance.
- Ensure `settings.yml` allows JSON format if running custom configurations.

## Sources
- [SearXNG Documentation](https://docs.searxng.org/)
- [SearXNG GitHub Repository](https://github.com/searxng/searxng)
