---
name: colibri
description: "Compile and run ultra-fast streaming MoE local model inference using the pure-C Colibri engine. Use when running minimal-footprint streaming model inference on CPU or lightweight machines."
---

# Colibri Pure-C MoE Streaming Engine

Minimalist Mixture-of-Experts (MoE) streaming inference engine implemented entirely in standard ANSI C without external runtime dependencies. Designed for embedded devices, lightweight servers, and instant local generation.

## Use this skill when
- Running local MoE inference with zero Python or CUDA runtime dependencies.
- Deploying compact streaming LLM services on constrained hardware or CI test runners.
- Benchmarking raw C matrix multiplication and token generation performance.

## Steps
1. **Compile Colibri from source**:
   Clone the repository and build using standard `make`:
   ```bash
   git clone https://github.com/JustVugg/colibri.git
   cd colibri && make
   ```
2. **Prepare quantized model weights**:
   Convert or download supported quantized MoE model checkpoints into Colibri format:
   ```bash
   ./colibri-convert --input weights.bin --output model.colibri
   ```
3. **Execute prompt inference**:
   Run single-turn prompt inference with streaming token output:
   ```bash
   ./colibri --model model.colibri --prompt "Write a quicksort in C" --max-tokens 256
   ```
4. **Start local streaming server**:
   Launch the embedded HTTP server for streaming API requests:
   ```bash
   ./colibri-server --port 8080 --model model.colibri
   ```

## Checks
- Verify compilation produces clean binaries without compiler warnings.
- Test token throughput with `./colibri --benchmark`.

## Pitfalls
- Ensure model architecture matches Colibri's supported MoE layer layout before loading.
- On Windows systems, compile via MinGW-w64 or WSL for POSIX pthread compatibility.

## Sources
- [Colibri GitHub Repository](https://github.com/JustVugg/colibri)
