import { QueryClient } from "@tanstack/react-query"

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 30_000,
      },
    },
  })
}

export const queryClient = createQueryClient()
