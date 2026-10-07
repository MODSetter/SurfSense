import { code } from "@streamdown/code"
import { createMathPlugin } from "@streamdown/math"

// Same code/math plugins chat uses (src/features/chat/message.tsx), shared
// by every artifact viewer that renders markdown through Streamdown.
export const streamdownPlugins = {
  code,
  math: createMathPlugin({ singleDollarTextMath: true }),
}

// Streamdown's default, as one object: a new one each render re-renders the
// whole document.
export const STREAMDOWN_LINK_SAFETY = { enabled: true }
