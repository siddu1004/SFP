---
name: react-colorful
description: "Integrate ultra-lightweight, zero-dependency color pickers in React apps using react-colorful. Use when adding color pickers (Hex, RGB, HSL, HSV) with keyboard accessibility, custom styling, or alpha support to React interfaces."
---

# react-colorful

A tiny (2.8 KB), dependency-free, accessible color picker component for React (`omgovich/react-colorful`). Supports HEX, RGB, RGBA, HSL, HSLA, HSV, and HSVA color formats.

## Use This Skill When

- Adding color picker widgets to React dashboards, design tools, or theme editors.
- Replacing heavy, bloated legacy color pickers with a clean, bundle-efficient alternative.
- Ensuring full keyboard navigation (`Arrow` keys) and screen reader accessibility for color controls.

## Installation

```bash
npm install react-colorful
```

## Component Implementation

```tsx
import React, { useState } from "react";
import { HexColorPicker, HexColorInput } from "react-colorful";

export function CustomColorPicker() {
  const [color, setColor] = useState("#3b82f6");

  return (
    <div className="flex flex-col gap-2 p-4 bg-white rounded-lg shadow-sm border">
      <HexColorPicker color={color} onChange={setColor} />
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono text-gray-500">HEX:</span>
        <HexColorInput
          color={color}
          onChange={setColor}
          prefixed
          className="px-2 py-1 border rounded text-xs font-mono uppercase"
        />
      </div>
    </div>
  );
}
```

## Checks & Best Practices

- [ ] Use `HexColorInput` or an accessible text field alongside the graphical picker so keyboard and screen-reader users can type values directly.
- [ ] For alpha channel transparency, import `RgbaColorPicker` or `HslaColorPicker` instead of `HexColorPicker`.
- [ ] Apply custom styling via standard CSS classes `.react-colorful`, `.react-colorful__saturation`, `.react-colorful__hue`.

## Sources

- [react-colorful Documentation](https://github.com/omgovich/react-colorful)
