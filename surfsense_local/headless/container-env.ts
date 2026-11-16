// What the container sets for every sidecar, where Electron sets it from being packaged.
import { join } from "node:path"

export function containerEnv(dataDir: string): Record<string, string> {
  return {
    // The bundled models are in the image; nothing downloads them at run time.
    HF_HUB_OFFLINE: "1",
    // A venv backend reads `sys.frozen` as false and would trust the checkout's unsigned list.
    SURFSENSE_LOCAL_SIGNED_REGISTRY: "1",
    // Where the API answers differently in a container, as the Claude dialog does.
    SURFSENSE_LOCAL_RUNTIME: "docker",
    // On the volume, so what a user installs in the container, such as Claude Code, keeps.
    HOME: join(dataDir, "home"),
  }
}
