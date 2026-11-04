import { Streamdown } from "streamdown"

import {
  STREAMDOWN_LINK_SAFETY,
  streamdownPlugins,
  UNTRUSTED_REHYPE_PLUGINS,
} from "@/features/studio/viewers/streamdown-config"

import { imagesAsTheirDescriptions } from "./citation-chunk-images"

// Raw and sanitize first, so an image written as HTML goes too; harden stays last.
const CHUNK_REHYPE_PLUGINS = [
  ...UNTRUSTED_REHYPE_PLUGINS.slice(0, -1),
  imagesAsTheirDescriptions,
  ...UNTRUSTED_REHYPE_PLUGINS.slice(-1),
]

/** A chunk of a source, as formatted text. Its text is a file's or a web page's own,
 *  so it loads no remote image, and a long address breaks rather than leave the card. */
export function CitationChunkText({ content }: { content: string }) {
  return (
    <div className="text-sm leading-6 wrap-anywhere *:first:mt-0 [&_h1]:text-base [&_h2]:text-base [&_h3]:text-sm">
      <Streamdown
        mode="static"
        controls={false}
        plugins={streamdownPlugins}
        rehypePlugins={CHUNK_REHYPE_PLUGINS}
        linkSafety={STREAMDOWN_LINK_SAFETY}
      >
        {content}
      </Streamdown>
    </div>
  )
}
