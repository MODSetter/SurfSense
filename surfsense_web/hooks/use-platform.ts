import { useContext } from "react";
import { PlatformContext, type PlatformContextValue } from "@/contexts/platform-context";

export function usePlatform(): Pick<PlatformContextValue, "isDesktop" | "isWeb"> {
	const { isDesktop, isWeb } = useContext(PlatformContext);
	return { isDesktop, isWeb };
}

export function useElectronAPI(): ElectronAPI | null {
	const { electronAPI } = useContext(PlatformContext);
	return electronAPI;
}
