import { useQuery } from "@tanstack/react-query"

export function useStorageState() {
  const bridge = window.surfsense?.storage
  return useQuery({
    queryKey: ["storage-state"],
    queryFn: () => bridge!.state(),
    enabled: bridge !== undefined,
  })
}
