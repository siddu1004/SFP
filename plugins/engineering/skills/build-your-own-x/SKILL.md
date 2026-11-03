---
name: build-your-own-x
description: "Recreate core technologies from scratch step-by-step: Git, Redis, Docker, SQLite, HTTP servers, or compilers. Use when building deep foundational systems, designing zero-dependency implementations, or mastering low-level software architecture."
---

# Build Your Own X

A step-by-step methodology for reconstructing foundational software technologies (databases, version control, compilers, container runtimes, protocol parsers) from first principles.

## Use This Skill When

- Implementing minimal, zero-dependency versions of fundamental systems (e.g. Git, Redis, SQLite, Docker, BitTorrent).
- Designing core data structures, storage engines, binary protocols, or execution virtual machines.
- Reverse-engineering open protocols (HTTP/1.1, RESP, DNS wire format) test-first.

## Step-by-Step Architecture

### 1. Identify the Minimal Kernel
Isolate the smallest atomic capability that provides functional utility:
- **Git**: Object store (`blob`, `tree`, `commit`) and content-addressable SHA storage.
- **Redis**: TCP server parsing RESP protocol, supporting `PING`, `SET`, `GET` in memory.
- **SQLite**: Page-based B-Tree file format and single-table linear scanner.
- **Docker**: Linux namespaces (`CLONE_NEWPID`, `CLONE_NEWNET`) and `chroot` root filesystem isolation.

### 2. Implement the Wire/File Protocol Test-First
Write tests for the binary or text protocol serialization and deserialization before writing the server logic:

```python
# Example: RESP protocol parsing in Python
def parse_resp(buffer: bytes):
    if not buffer:
        return None, buffer
    prefix = buffer[0:1]
    if prefix == b"+": # Simple string
        line, rest = buffer[1:].split(b"\r\n", 1)
        return line.decode(), rest
    elif prefix == b":": # Integer
        line, rest = buffer[1:].split(b"\r\n", 1)
        return int(line), rest
    elif prefix == b"$": # Bulk string
        line, rest = buffer[1:].split(b"\r\n", 1)
        length = int(line)
        if length == -1: return None, rest
        content = rest[:length]
        return content, rest[length+2:]
    raise ValueError(f"Unknown RESP prefix: {prefix}")
```

### 3. Layer the Engine Above the Protocol
Connect the protocol parser to an in-memory or on-disk data structure with clean boundaries.

### 4. Verify Conformance with Real Clients
Test the custom implementation against standard official tooling (e.g., test your Redis clone with `redis-cli`, your Git clone with `git log`).

## Verification Checklist

- [ ] Core protocol parsing conforms strictly to RFC or official format specs.
- [ ] End-to-end tests verify compatibility using the official reference CLI tool.
- [ ] Edge cases (empty payloads, large buffers, unexpected disconnects) are handled gracefully.

## Pitfalls

- **Over-Scoping Early**: Do not implement auxiliary commands or optimizations until the core loop is passing tests.
- **Ignoring Byte Alignment**: Binary formats require exact endianness and padding handling.

## Sources

- [CodeCrafters Build Your Own X](https://github.com/codecrafters-io/build-your-own-x)
