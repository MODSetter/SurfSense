import { code } from "@streamdown/code"
import { createMathPlugin } from "@streamdown/math"

// Same code/math plugins chat uses (src/features/chat/message.tsx), shared
// by every artifact viewer that renders markdown through Streamdown.
export const streamdownPlugins = {
  code,
  math: createMathPlugin({ singleDollarTextMath: true }),
}
