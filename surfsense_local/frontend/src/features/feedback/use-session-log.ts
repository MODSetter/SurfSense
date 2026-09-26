import { useQuery } from "@tanstack/react-query"

// The preload bridge, absent in a bare browser.
export function sessionLogBridge() {
  return typeof window === "undefined"
    ? undefined
    : window.surfsense?.sessionLog
}

// Polled while shown, so it reads like a console.
export function useSessionLog(shown: boolean) {
  const bridge = sessionLogBridge()
  return useQuery({
    queryKey: ["session-log"],
    queryFn: () => bridge!.read(),
    enabled: shown && bridge !== undefined,
    refetchInterval: 1000,
    staleTime: 0,
  })
}
