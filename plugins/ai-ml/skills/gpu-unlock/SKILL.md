---
name: gpu-unlock
description: "Unlocks tensor cores on GeForce cards to boost AI performance without flashing firmware or changing drivers. Use when a GeForce RTX 20/30/40 card on Linux runs FP16/BF16 AI work slower than expected and the user asks about unlocking full tensor-core speed."
---

> Written for SFP in its own words from the project at https://github.com/Zagitta/gpu-unlock (upstream license: none).

# GPU Unlock (gpu-unlock): understand it before anyone runs it

## Use this skill when
- The user asks why their GeForce RTX 20/30/40 card runs FP16, BF16 or TF32 AI work at half speed on Linux.
- The user is considering gpu-unlock and wants to know what it changes and how to undo it.

## What it is
gpu-unlock is a Linux kernel module that lifts the reduced tensor-core rate on consumer GeForce cards at boot, before the NVIDIA driver loads. It does not flash firmware, but it does load a third-party kernel module and change the kernel command line, so a mistake can leave the system unbootable.

## Steps
1. Do not install or enable it yourself. Explain what it does and let the user decide and run every command.
2. Check the prerequisites with the user: Linux (not Windows or macOS), a supported RTX 20/30/40 card (see the repository's list), a recent backup, and a known way to reach the boot menu to undo a bad change.
3. Measure first: run the user's real workload (or a matmul benchmark in FP16/BF16) and record its throughput, so the effect can be proven.
4. Point the user to the repository's own install instructions, including which bootloader file holds the kernel command line on their distribution.
5. Give the rollback before they start: remove `gpu_unlock.targets=all` from the kernel command line (or choose the previous entry in the boot menu), then uninstall the module the way the repository describes.
6. After they reboot, re-run the same benchmark and compare with step 3.

## Checks
- The benchmark from step 3 is faster after the change; if not, roll back.
- The system boots normally and `nvidia-smi` shows the card.

## Pitfalls
- Laptops can lose the unlock when the dedicated GPU powers down.
- Kernel or driver updates can break a third-party module; re-check after updates.
- Never run these steps on a machine the user has not explicitly chosen.
