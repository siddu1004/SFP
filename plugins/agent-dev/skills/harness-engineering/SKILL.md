---
name: harness-engineering
description: "Design, test, and optimize AI agent execution harnesses, test fixtures, action spaces, and evaluation gates. Use when building agent evaluation loops, configuring autonomous runtime environments, or optimizing agent action spaces."
---

# Agent Harness Engineering

A guide to constructing robust evaluation harnesses, sandboxed execution environments, and observation feedback loops for autonomous AI coding agents.

## Use This Skill When

- Designing, structuring, or debugging an autonomous AI agent execution harness.
- Setting up deterministic test fixtures, mock environments, or synthetic regression gates.
- Optimizing observation formatting and token budget boundaries for agent tool outputs.
- Preventing prompt leakage, environment pollution, and non-deterministic agent loop failures.

## Core Architectural Pillars

1. **State Isolation & Clean Teardown**:
   - Every agent run starts from an immutable baseline snapshot or isolated Git branch / Docker container.
   - Teardown restores state unconditionally, ensuring run $N$ never leaks state into run $N+1$.
2. **Compact Observation Space**:
   - Agent tool outputs must be compressed to task-relevant evidence.
   - Long traces, dumps, and giant logs must be truncated with explicit head/tail windows and byte counts.
3. **Deterministic Verification Gates**:
   - Agent success must be graded by reproducible test suites or static verification scripts, not by LLM self-evaluation alone.
   - Tests execute in a sub-process sandbox with strict wall-clock timeouts.

## Implementation Steps

### 1. Structure the Test Fixture

```python
import subprocess
import tempfile
import os

class AgentHarness:
    def __init__(self, fixture_path: str):
        self.fixture_path = fixture_path
        self.temp_dir = tempfile.TemporaryDirectory()

    def setup(self):
        # Unpack clean fixture snapshot
        subprocess.run(["tar", "-xzf", self.fixture_path, "-C", self.temp_dir.name], check=True)
        return self.temp_dir.name

    def teardown(self):
        self.temp_dir.cleanup()
```

### 2. Format Tool Observations

```python
def format_observation(output: str, max_chars: int = 2000) -> str:
    """Format tool execution output to preserve agent context."""
    if len(output) <= max_chars:
        return output
    half = max_chars // 2
    return f"{output[:half]}\n... [truncated {len(output) - max_chars} characters] ...\n{output[-half:]}"
```

### 3. Evaluate Against Objective Acceptance Criteria

```bash
# Run isolated evaluation suite
pytest tests/eval/test_task_acceptance.py -v --timeout=30
```

## Checks & Verification

- [ ] Workspace state is isolated and tears down cleanly without side effects.
- [ ] Agent tools fail closed with structured error JSON when timeouts or permission denials occur.
- [ ] Evaluations enforce reproducible ground-truth assertions (status codes, file diffs, test passes).

## Pitfalls to Avoid

- **Unbounded Context Bloat**: Emitting megabytes of compiler or linter errors into agent context crashes token budgets.
- **Flaky Evals**: Network-dependent assertions cause intermittent false negatives in autonomous loops.
- **Missing Resource Limits**: Agent sub-processes must have CPU and memory ceilings to prevent runaway processes.

## Sources

- [AgentBench: Evaluating LLMs as Agents](https://github.com/THUDM/AgentBench)
- [SWE-bench Benchmark Architecture](https://github.com/princeton-nlp/SWE-bench)
