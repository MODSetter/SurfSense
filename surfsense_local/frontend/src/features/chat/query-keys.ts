export const chatKeys = {
  all: ["chat"] as const,
  threads: (workspaceId: number) =>
    [...chatKeys.all, "threads", workspaceId] as const,
  messages: (threadId: number) =>
    [...chatKeys.all, "messages", threadId] as const,
}
