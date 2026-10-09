import { buttonVariants } from "@/components/ui/button"
import { Download01Icon } from "@/components/ui/icons"
import { intl } from "@/i18n/intl"

import { isWordCopy, revisedCopyDownloadUrl, type Revision } from "./api"

/** The copy's two downloads, in place of the file's own: with its changes,
 *  and for Word also clean, every change accepted and no comments. */
export function RevisedCopyDownloads({
  artifactId,
  revision,
}: {
  artifactId: number
  revision: Revision
}) {
  const link = (
    variant: "changes" | "clean",
    label: string,
    suffix: string
  ) => (
    // A plain link: Base UI's Button would give it role="button".
    <a
      key={variant}
      href={revisedCopyDownloadUrl(artifactId, variant, suffix)}
      download
      className={buttonVariants({ variant: "secondary", size: "sm" })}
    >
      <Download01Icon data-icon="inline-start" />
      {label}
    </a>
  )
  return (
    <>
      {link(
        "changes",
        intl.formatMessage({
          id: "studio_revised_copy_download_changes_link",
          defaultMessage: "With changes",
        }),
        intl.formatMessage({
          id: "studio_revised_copy_changes_suffix_label",
          defaultMessage: "revised",
          description:
            "Word in a downloaded file's name: MSA (revised v2).docx. No characters a file name cannot hold.",
        })
      )}
      {isWordCopy(revision)
        ? link(
            "clean",
            intl.formatMessage({
              id: "studio_revised_copy_download_clean_link",
              defaultMessage: "Clean",
            }),
            intl.formatMessage({
              id: "studio_revised_copy_clean_suffix_label",
              defaultMessage: "clean",
              description:
                "Word in a downloaded file's name: MSA (clean v2).docx. No characters a file name cannot hold.",
            })
          )
        : null}
    </>
  )
}
