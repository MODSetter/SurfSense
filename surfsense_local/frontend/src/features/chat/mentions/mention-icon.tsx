import { FileIcon, Folder01Icon } from "@/components/ui/icons"
import { FORMAT_ICONS } from "@/features/studio/studio-formats"

const ARTIFACT = "artifact-"

/** A folder, a file, or an artifact's format, from what a mention carries. */
export function MentionIcon({
  id,
  type,
  className,
}: {
  id: string
  type: string
  className?: string
}) {
  const Icon = id.startsWith("folder:")
    ? Folder01Icon
    : type.startsWith(ARTIFACT)
      ? (FORMAT_ICONS[type.slice(ARTIFACT.length)] ?? FileIcon)
      : FileIcon
  return <Icon className={className} />
}
