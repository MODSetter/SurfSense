export type Health = {
  status: "ok"
}

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch("/health", { signal })
  if (!response.ok) {
    throw new Error(`health responded ${response.status}`)
  }
  return response.json()
}
