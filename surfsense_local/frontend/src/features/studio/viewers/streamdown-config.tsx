import { createMathPlugin } from "@streamdown/math"
import type { LinkSafetyConfig } from "streamdown"

import { ExternalLinkDialog } from "@/features/external-links/external-link-dialog"

import { codeHighlighter } from "./code-highlighter"

const math = createMathPlugin({ singleDollarTextMath: true })

// The code and math plugins every Streamdown in the app renders with: chat
// replies, the reasoning trace and the artifact viewers.
export const streamdownPlugins = { code: codeHighlighter, math }

// While text streams in, code stays plain: highlighting it would tokenize every
// partial state of a growing block. The same math instance, or every block
// re-parses when a finished reply switches to the set above.
export const streamingStreamdownPlugins = { math }

// Every link in rendered content asks first, in the app's own popup rather than
// Streamdown's: translated, and opening through the desktop app's confirmed-link
// call. One object: a new one each render re-renders the whole document.
export const STREAMDOWN_LINK_SAFETY: LinkSafetyConfig = {
  enabled: true,
  renderModal: ({ isOpen, onClose, url }) => (
    <ExternalLinkDialog
      url={url}
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    />
  ),
}
