import { fileUrl, type ArtifactDetail } from "../api"

// The fallback viewer: any format without a dedicated entry in the viewer
// registry renders here, so a new backend format never breaks the panel.
export function DocumentViewer({ artifact }: { artifact: ArtifactDetail }) {
  const primary = artifact.files.find((file) => file.role === "primary")

  return (
    <div className="space-y-4">
      {primary ? <Preview artifact={artifact} primary={primary} /> : null}
      <p className="text-sm leading-6 whitespace-pre-wrap">
        {artifact.content || "This artifact has no text body."}
      </p>
    </div>
  )
}

function Preview({
  artifact,
  primary,
}: {
  artifact: ArtifactDetail
  primary: ArtifactDetail["files"][number]
}) {
  const src = fileUrl(artifact.id, primary.role)
  if (primary.mime_type.startsWith("audio/")) {
    // biome-ignore lint/a11y/useMediaCaption: The generated transcript is rendered directly below the player.
    return <audio className="w-full" controls src={src} />
  }
  if (primary.mime_type.startsWith("image/")) {
    return (
      <img
        className="mx-auto max-w-full outline outline-[oklch(0_0_0/0.1)] dark:outline-[oklch(1_0_0/0.1)]"
        alt={artifact.title}
        src={src}
      />
    )
  }
  return null
}
