import { Alert, AlertDescription } from "@/components/ui/alert"
import { CircleAlertIcon } from "@/components/ui/icons"
import { Skeleton } from "@/components/ui/skeleton"
import { SettingsSection } from "@/features/settings/settings-section"
import { intl } from "@/i18n/intl"

import { useEmbeddingIndex } from "./use-embedding-index"

/**
 * The search model, shown and never changed: every passage in the library was
 * embedded by it, and changing it means embedding them all again, which is
 * not built yet.
 */
export function EmbeddingSettings() {
  const index = useEmbeddingIndex()
  const active = index.data?.active ?? null

  const body = () => {
    if (index.isPending) return <Skeleton className="h-12 w-full" />
    if (index.error) {
      return (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertDescription>{index.error.message}</AlertDescription>
        </Alert>
      )
    }
    if (!active) return null
    return (
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-0.5">
          <h3 className="text-sm font-medium">{active.name}</h3>
          {active.spec.identified !== "measured" ? (
            <p className="text-sm text-muted-foreground">
              {intl.formatMessage({
                id: "embedding_settings_untested_body",
                defaultMessage: "Not tested by SurfSense",
              })}
            </p>
          ) : null}
          <p className="text-sm text-muted-foreground">
            {intl.formatMessage(
              {
                id: "embedding_settings_width_body",
                defaultMessage: "Vector size: {dimension, number}",
              },
              { dimension: active.spec.dimension }
            )}
          </p>
        </div>
        <Alert variant="secondary">
          <CircleAlertIcon />
          <AlertDescription>
            {intl.formatMessage({
              id: "embedding_settings_fixed_body",
              defaultMessage:
                "Chosen during setup and kept for your whole library. Changing it is not available yet.",
            })}
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <SettingsSection
      title={intl.formatMessage({
        id: "embedding_settings_title",
        defaultMessage: "Embedding",
      })}
      description={intl.formatMessage({
        id: "embedding_settings_body",
        defaultMessage:
          "The model that turns your documents into something search can compare.",
      })}
    >
      {body()}
    </SettingsSection>
  )
}
