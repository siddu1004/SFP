---
name: public-apis
description: Find a free public API for any need from a bundled list of about 2,100 APIs in 51 categories (animals, books, finance, geocoding, government, health, machine learning, music, news, open data, science, sports, transportation, weather and more), with auth type, HTTPS and CORS for each, via a search script. Use when the user needs an API or data source, asks "is there an API for...", wants free or no-key APIs, or is choosing an API for a prototype, hackathon, app or demo.
---

# Public APIs

A bundled copy of the [public-apis](https://github.com/public-apis/public-apis) list, with a script to search it. Do not answer "is there an API for X" from memory: search first.

## Search

Run the script that sits next to this file (`scripts/find_api.py`, relative to this skill's folder). It needs only Python 3.

```bash
python3 scripts/find_api.py weather                          # keywords must all match
python3 scripts/find_api.py "cat facts" --auth none --cors yes
python3 scripts/find_api.py --category Finance --https yes --limit 20
python3 scripts/find_api.py --categories                     # all 51 categories with counts
python3 scripts/find_api.py music --json                     # machine-readable
```

Filters: `--auth none|apiKey|OAuth|any`, `--cors yes|no|unknown|any`, `--https yes|no|any`, `--limit N`.

If nothing matches, use fewer or broader words, a synonym ("forecast" for "weather"), or browse a category. Without Python, search `reference/public-apis.md` directly: each category is a `### Name` heading followed by a table of `| [Name](docs url) | Description | Auth | HTTPS | CORS |`.

## Choose

- Give 3 to 6 of the best matches, each with its link, what it offers, and its auth, HTTPS and CORS values.
- Fit the user's constraints. Code running in a browser needs `CORS: Yes`. With no backend to hold a secret, prefer `Auth: No`. Always prefer `HTTPS: Yes`.
- The list is community-maintained, so an API can change or shut down. Say so, and check the docs link before the user builds on it.
- The "APIs Covered Under APILayer Suite" block at the top is sponsored. Treat it like any other entry.

## Use

Fetch an API's docs page for the exact endpoints and parameters before writing code against it. Keys go in environment variables, never in committed code.
