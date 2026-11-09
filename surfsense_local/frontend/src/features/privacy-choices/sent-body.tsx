/** A request or report exactly as it goes over the wire, scrollable when long. */
export function SentBody({ label, text }: { label: string; text: string }) {
  return (
    <pre
      aria-label={label}
      tabIndex={0}
      className="max-h-56 overflow-auto rounded-lg bg-muted p-3 font-mono text-xs leading-5 whitespace-pre select-text"
    >
      {text}
    </pre>
  )
}
