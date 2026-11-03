---
name: openmontage
description: "Create and render programmatic video montages from video clips, audio tracks, and timeline specs using OpenMontage. Use when automating video compilation, generating clip reels, or synchronizing video transitions."
---

# OpenMontage Video Pipeline

Programmatic video montage generation CLI powered by FFmpeg and Remotion. Enables agents to compose video edits, clip transitions, subtitles, and soundtrack timing via JSON timeline specifications.

## Use this skill when
- Generating video summaries, highlight reels, or demo walk-throughs programmatically.
- Composing automated social media clips or animated product teasers from source footage.
- Synchronizing video cuts and transitions to audio beats or subtitle timestamps.

## Steps
1. **Define the montage timeline**:
   Create a timeline specification JSON (`montage.json`) specifying source clips, cut points, transitions, and overlays:
   ```json
   {
     "output": "dist/summary.mp4",
     "tracks": [
       { "src": "raw/intro.mp4", "start": 0, "duration": 5.0 },
       { "src": "raw/demo.mp4", "start": 2.5, "duration": 10.0, "transition": "fade" }
     ]
   }
   ```
2. **Preview video frames**:
   Render a single frame snapshot to verify composition and color grading:
   ```bash
   openmontage preview --timeline montage.json --at 00:00:03.000
   ```
3. **Execute full montage render**:
   Render the complete video composition with hardware-accelerated encoding:
   ```bash
   openmontage render --timeline montage.json --preset high
   ```
4. **Validate output video**:
   Verify video stream codec, resolution, and audio synchronization with FFprobe.

## Checks
- Confirm FFmpeg is installed and accessible in system PATH.
- Verify all referenced source media files exist on disk before rendering.
- Verify output MP4 container plays smoothly without dropped frames.

## Pitfalls
- Mixing video clips with different aspect ratios or frame rates without explicit scaling rules can distort output.
- Rendering high-resolution 4K video consumes significant CPU/GPU memory; test with low-resolution proxies first.

## Sources
- [OpenMontage GitHub Repository](https://github.com/calesthio/OpenMontage)
