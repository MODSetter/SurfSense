import { useQuery } from "@tanstack/react-query"

// The preload bridge, absent in a bare browser and in the web build.
export function aboutBridge() {
  return typeof window === "undefined" ? undefined : window.surfsense?.about
}

// Fixed for the life of the process, so it is read once.
export function useAppDetails() {
  const about = aboutBridge()
  return useQuery({
    queryKey: ["app-details"],
    queryFn: () => about!.details(),
    enabled: about !== undefined,
    staleTime: Infinity,
  })
}
