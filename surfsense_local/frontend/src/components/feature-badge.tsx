import { Badge } from "@/components/ui/badge"
import { intl } from "@/i18n/intl"

export type FeatureStage = "new" | "coming-soon"

const LABELS: Record<FeatureStage, () => string> = {
  new: () =>
    intl.formatMessage({
      id: "app_feature_badge_new_label",
      defaultMessage: "New",
    }),
  "coming-soon": () =>
    intl.formatMessage({
      id: "app_feature_badge_coming_soon_label",
      defaultMessage: "Coming soon",
    }),
}

/** Marks a feature that just arrived, or one shown before it works. */
export function FeatureBadge({ stage }: { stage: FeatureStage }) {
  return (
    <Badge variant="secondary" className="rounded-md">
      {LABELS[stage]()}
    </Badge>
  )
}
