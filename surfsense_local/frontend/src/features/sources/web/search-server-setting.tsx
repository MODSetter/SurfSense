import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useId, useState, type SubmitEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { intl } from "@/i18n/intl"
import { ApiError } from "@/lib/api"

import {
  chooseSearchServer,
  readSearchServer,
  searchServerQueryKey,
} from "./search-server-api"

/** Settings › Network: the SearXNG server Add from the web searches with. */
export function SearchServerSetting() {
  const headingId = useId()
  const queryClient = useQueryClient()
  const server = useQuery({
    queryKey: searchServerQueryKey,
    queryFn: ({ signal }) => readSearchServer(signal),
  })
  // Null until the user types; then the field shows what they typed.
  const [draft, setDraft] = useState<string | null>(null)
  const choose = useMutation({
    mutationFn: chooseSearchServer,
    onSuccess: (chosen) => {
      queryClient.setQueryData(searchServerQueryKey, chosen)
      setDraft(null)
    },
  })
  const saved = server.data?.url ?? ""
  const shown = draft ?? saved

  const save = (event: SubmitEvent) => {
    event.preventDefault()
    choose.mutate(shown.trim() || null)
  }

  return (
    <div className="mt-8 flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h3 id={headingId} className="text-sm font-medium">
          {intl.formatMessage({
            id: "sources_search_server_title",
            defaultMessage: "Web search",
          })}
        </h3>
        <p className="text-sm text-pretty text-muted-foreground">
          {intl.formatMessage({
            id: "sources_search_server_body",
            defaultMessage:
              "Add from the web searches through a SearXNG server: SurfSense’s own, unless you name another, such as your organization’s.",
          })}
        </p>
      </div>
      <form className="flex gap-2" onSubmit={save}>
        <Input
          aria-labelledby={headingId}
          value={shown}
          placeholder={server.data?.default_url}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button
          type="submit"
          disabled={shown.trim() === saved || choose.isPending}
        >
          {intl.formatMessage({
            id: "sources_search_server_save_button",
            defaultMessage: "Save",
          })}
        </Button>
        {saved ? (
          <Button
            type="button"
            variant="outline"
            disabled={choose.isPending}
            onClick={() => choose.mutate(null)}
          >
            {intl.formatMessage({
              id: "sources_search_server_reset_button",
              defaultMessage: "Use SurfSense’s",
            })}
          </Button>
        ) : null}
      </form>
      {choose.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {/* Only the API's address check answers 422; a good address can fail too. */}
          {choose.error instanceof ApiError && choose.error.status === 422
            ? intl.formatMessage({
                id: "sources_search_server_invalid_error",
                defaultMessage:
                  "Enter the server’s address, starting with https:// or http://.",
              })
            : intl.formatMessage({
                id: "sources_search_server_save_error",
                defaultMessage: "Couldn’t save the search server. Try again.",
              })}
        </p>
      ) : null}
      <p className="text-xs text-pretty text-muted-foreground">
        {intl.formatMessage({
          id: "sources_search_server_json_body",
          defaultMessage:
            "The server must answer in JSON: its settings.yml lists json under search.formats.",
        })}
      </p>
    </div>
  )
}
