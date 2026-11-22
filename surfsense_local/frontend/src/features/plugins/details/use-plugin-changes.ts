import { useMutation, useQueryClient } from "@tanstack/react-query"

import {
  checkPlugin,
  disconnectPlugin,
  pluginsQueryKey,
  removePlugin,
  setPluginEnabled,
  setThirdPartyAllowed,
  setTool,
  thirdPartyQueryKey,
  type ToolChange,
} from "../api"

/** Every change the screen makes; each reads the plugins back once it lands. */
export function usePluginChanges() {
  const queryClient = useQueryClient()
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: pluginsQueryKey })

  return {
    tool: useMutation({
      mutationFn: ({
        plugin,
        tool,
        change,
      }: {
        plugin: string
        tool: string
        change: ToolChange
      }) => setTool(plugin, tool, change),
      onSettled: refresh,
    }),
    plugin: useMutation({
      mutationFn: ({ plugin, enabled }: { plugin: string; enabled: boolean }) =>
        setPluginEnabled(plugin, enabled),
      onSettled: refresh,
    }),
    check: useMutation({
      mutationFn: (plugin: string) => checkPlugin(plugin),
      onSettled: refresh,
    }),
    disconnect: useMutation({
      mutationFn: (plugin: string) => disconnectPlugin(plugin),
      onSettled: refresh,
    }),
    remove: useMutation({
      mutationFn: (plugin: string) => removePlugin(plugin),
      onSettled: refresh,
    }),
    thirdParty: useMutation({
      mutationFn: (allowed: boolean) => setThirdPartyAllowed(allowed),
      onSettled: () =>
        queryClient.invalidateQueries({ queryKey: thirdPartyQueryKey }),
    }),
  }
}
