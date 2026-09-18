import { fileUrl, type ArtifactDetail } from "../api"

// Image and infographic both come from an image-generation model: one
// picture as the primary file, nothing else worth showing. `content` for
// these formats is generation input (a raw prompt, or the brief painted
// into the picture), not user-facing body text, so it's never rendered.
// Like the other canvas viewers (mindmap, xlsx), it sits flush against the
// panel edges rather than taking the flowing-content padding.
export function MediaViewer({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const src = primary ? fileUrl(artifact.id, primary.role) : null

  return src ? <img className="w-full" alt={artifact.title} src={src} /> : null
}
