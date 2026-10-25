import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { errorToast } from "@/features/feedback/error-toast"
import { intl } from "@/i18n/intl"

import { aboutBridge } from "./use-app-details"

// The installer picks where the program goes; this says where the data stays (#2288).
export function DataFolder() {
  const about = aboutBridge()
  const { data: folder } = useQuery({
    queryKey: ["data-folder"],
    queryFn: () => about!.dataFolder!(),
    enabled: about?.dataFolder !== undefined,
    staleTime: Infinity,
  })

  if (!folder) return null

  const open = async () => {
    const reason = await about!.openDataFolder!()
    if (reason) {
      errorToast(
        intl.formatMessage({
          id: "about_data_folder_open_error",
          defaultMessage: "Couldn’t open the data folder",
        }),
        { description: reason }
      )
    }
  }

  return (
    <div className="mt-8 flex items-start justify-between gap-8">
      <div className="flex min-w-0 flex-col gap-1">
        <h3 className="text-sm font-medium">
          {intl.formatMessage({
            id: "about_data_folder_title",
            defaultMessage: "Your data",
          })}
        </h3>
        <p className="text-sm text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "about_data_folder_body",
            defaultMessage:
              "Models, workspaces and settings are kept here, not in the folder SurfSense is installed in.",
          })}
        </p>
        <code className="text-sm break-all">{folder}</code>
      </div>
      <Button type="button" variant="outline" onClick={() => void open()}>
        {intl.formatMessage({
          id: "about_data_folder_open_button",
          defaultMessage: "Open folder",
        })}
      </Button>
    </div>
  )
}
