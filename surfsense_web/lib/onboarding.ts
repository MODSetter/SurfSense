export function isLlmOnboardingComplete(
	agentLlmId: number | null | undefined,
	hasGlobalConfigs: boolean
): boolean {
	if (agentLlmId === null || agentLlmId === undefined) return false;
	if (agentLlmId === 0) return hasGlobalConfigs;
	return true;
}
