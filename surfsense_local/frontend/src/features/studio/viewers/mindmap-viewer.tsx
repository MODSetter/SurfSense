import { Transformer } from "markmap-lib"
import { Markmap } from "markmap-view"
import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { Button } from "@/components/ui/button"
import { ArrowExpand01Icon } from "@/components/ui/icons"

interface TreeNode {
  label: string
  children: TreeNode[]
}

// Markdown only: a generated outline must not inject markup into the map.
const transformer = new Transformer([])
transformer.md.set({ html: false, linkify: false })
transformer.md.renderer.rules.link_open = () => ""
transformer.md.renderer.rules.link_close = () => ""
transformer.md.renderer.rules.image = (
  tokens: { content: string }[],
  index: number
) => transformer.md.utils.escapeHtml(tokens[index]?.content ?? "")

function toTree(node: { content?: unknown; children?: unknown }): TreeNode {
  const html = typeof node.content === "string" ? node.content : ""
  const label =
    new DOMParser()
      .parseFromString(html, "text/html")
      .body.textContent?.trim() ?? ""
  const children = Array.isArray(node.children) ? node.children : []
  return { label, children: children.map(toTree) }
}

function TreeItem({ node }: { node: TreeNode }) {
  return (
    <li>
      <span>{node.label}</span>
      {node.children.length > 0 ? (
        <ul>
          {node.children.map((child, index) => (
            <TreeItem key={`${index}-${child.label}`} node={child} />
          ))}
        </ul>
      ) : null}
    </li>
  )
}

export function MindmapViewer({
  markdown,
  actionsContainer,
}: {
  markdown: string
  actionsContainer: HTMLElement | null
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const markmapRef = useRef<Markmap | null>(null)
  const [tree, setTree] = useState<TreeNode | null>(null)

  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const markmap = Markmap.create(svg, {
      initialExpandLevel: -1,
      pan: true,
      zoom: true,
    })
    markmapRef.current = markmap
    return () => {
      markmapRef.current = null
      markmap.destroy()
    }
  }, [])

  useEffect(() => {
    const markmap = markmapRef.current
    if (!markmap) return
    const { root } = transformer.transform(markdown)
    setTree(toTree(root))
    void Promise.resolve(markmap.setData(root)).then(() => markmap.fit())
  }, [markdown])

  const fitButton = (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      aria-label="Fit mind map"
      className="text-muted-foreground"
      onClick={() => void markmapRef.current?.fit()}
    >
      <ArrowExpand01Icon />
    </Button>
  )

  return (
    <div className="relative h-full min-h-80 overflow-hidden bg-white">
      <svg
        ref={svgRef}
        className="absolute inset-0 h-full w-full touch-none"
        aria-hidden="true"
        focusable="false"
      />
      {actionsContainer ? createPortal(fitButton, actionsContainer) : null}
      {tree ? (
        <ul className="sr-only" aria-label="Mind map">
          <TreeItem node={tree} />
        </ul>
      ) : null}
    </div>
  )
}
