---
name: difftastic
description: "Perform syntax-aware structural diffing on source code using Difftastic (difft). Compares code based on AST structure rather than lines. Use when reviewing syntactic changes, inspecting complex refactors, or comparing nested code blocks across files."
---

# Difftastic Structural Diff

Structural code diffing powered by Difftastic (`difft`). Unlike line-by-line diff tools, Difftastic parses source code using tree-sitter grammars to compare abstract syntax trees, ignoring trivial whitespace or formatting changes while highlighting meaningful structural transformations.

## Use This Skill When

- Reviewing code changes that include reformatting, renamed variables, or indentation shifts.
- Comparing refactored functions across commits or files to verify AST preservation.
- Diagnosing complex syntax changes across 40+ programming languages.

## Step-by-Step Usage

### 1. Check Installation

```bash
difft --version
```

If not installed:
- Via Cargo: `cargo install --locked difftastic`
- Via Homebrew: `brew install difftastic`

### 2. Compare Files

```bash
# Structural diff of two files
difft old_file.py new_file.py

# Structural diff of a Git revision
git difftool --tool=difft HEAD~1
```

### 3. Display Settings for Automation

```bash
# Display compact summary with color disabled for agent consumption
difft --color=never --display=inline old.rs new.rs
```

## Checks & Verification

- [ ] Verify both files parse cleanly without syntax errors (Difftastic falls back to line-diff if parsing fails).
- [ ] Confirm syntax changes are highlighted at the node level (expressions, parameters, blocks).

## Sources

- [Difftastic Manual](https://difftastic.wilfred.me.uk/)
- [Difftastic GitHub Repository](https://github.com/Wilfred/difftastic)
