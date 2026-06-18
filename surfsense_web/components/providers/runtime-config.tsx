"use client";

import { createContext, useContext } from "react";

export type AuthType = "LOCAL" | "GOOGLE" | string;
export type DeploymentMode = "self-hosted" | "cloud" | string;

export interface RuntimeConfigValue {
	authType: AuthType;
	etlService: string;
	deploymentMode: DeploymentMode;
}

const RuntimeConfigContext = createContext<RuntimeConfigValue | null>(null);

export function RuntimeConfigProvider({
	value,
	children,
}: {
	value: RuntimeConfigValue;
	children: React.ReactNode;
}) {
	return <RuntimeConfigContext.Provider value={value}>{children}</RuntimeConfigContext.Provider>;
}

export function useRuntimeConfig() {
	const context = useContext(RuntimeConfigContext);
	if (!context) {
		throw new Error("useRuntimeConfig must be used within RuntimeConfigProvider");
	}
	return context;
}

export function useIsLocalAuth() {
	return useRuntimeConfig().authType === "LOCAL";
}

export function useIsGoogleAuth() {
	return useRuntimeConfig().authType === "GOOGLE";
}

export function useIsSelfHosted() {
	return useRuntimeConfig().deploymentMode === "self-hosted";
}

export function useIsCloud() {
	return useRuntimeConfig().deploymentMode === "cloud";
}
