import { fileUrl, type ArtifactDetail } from "../api"

// Image and infographic both come from an image-generation model: one
// picture as the primary file, nothing else worth showing. `content` for
// these formats is generation input (a raw prompt, or the brief painted
// into the picture), not user-facing body text, so it's never rendered.
export function MediaViewer({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")
  const src = primary ? fileUrl(artifact.id, primary.role) : null

  return src ? (
    <img
      className="mx-auto max-w-full rounded-lg outline outline-[oklch(0_0_0/0.1)] dark:outline-[oklch(1_0_0/0.1)]"
      alt={artifact.title}
      src={src}
    />
  ) : null
}
