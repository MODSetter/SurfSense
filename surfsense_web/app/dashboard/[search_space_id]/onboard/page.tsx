"use client";

import { FileText, MessageSquare, UserPlus, Users } from "lucide-react";
import { motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { OnboardActionCard } from "@/components/onboard/onboard-action-card";
import { OnboardAdvancedSettings } from "@/components/onboard/onboard-advanced-settings";
import { OnboardHeader } from "@/components/onboard/onboard-header";
import { OnboardLLMSetup } from "@/components/onboard/onboard-llm-setup";
import { OnboardLoading } from "@/components/onboard/onboard-loading";
import { OnboardStats } from "@/components/onboard/onboard-stats";
import { getBearerToken, redirectToLogin } from "@/lib/auth-utils";
import { useAtomValue } from "jotai";
import { llmConfigsAtom, globalLLMConfigsAtom, llmPreferencesAtom } from "@/atoms/llm-config/llm-config-query.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/llm-config/llm-config-mutation.atoms";
import { useMemo } from "react";

const OnboardPage = () => {
	const t = useTranslations("onboard");
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	const { data: llmConfigs = [], isFetching: configsLoading, refetch: refreshConfigs } = useAtomValue(llmConfigsAtom);
	const { data: globalConfigs = [], isFetching: globalConfigsLoading } = useAtomValue(globalLLMConfigsAtom);
	const { data: preferences = {}, isFetching: preferencesLoading, refetch: refreshPreferences } = useAtomValue(llmPreferencesAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);
	
	// Compute isOnboardingComplete
	const isOnboardingComplete = useMemo(() => {
		return () => !!(
			preferences.long_context_llm_id &&
			preferences.fast_llm_id &&
			preferences.strategic_llm_id
		);
	}, [preferences]);

	const [isAutoConfiguring, setIsAutoConfiguring] = useState(false);
	const [autoConfigComplete, setAutoConfigComplete] = useState(false);
	const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
	const [showPromptSettings, setShowPromptSettings] = useState(false);

	const handleRefreshPreferences = useCallback(async () => {
		await refreshPreferences()
	},[])

	// Track if we've already attempted auto-configuration
	const hasAttemptedAutoConfig = useRef(false);

	// Track if onboarding was complete on initial mount
	const wasCompleteOnMount = useRef<boolean | null>(null);
	const hasCheckedInitialState = useRef(false);

	// Check if user is authenticated
	useEffect(() => {
		const token = getBearerToken();
		if (!token) {
			// Save current path and redirect to login
			redirectToLogin();
			return;
		}
	}, []);

	// Capture onboarding state on first load
	useEffect(() => {
		if (
			!hasCheckedInitialState.current &&
			!preferencesLoading &&
			!configsLoading &&
			!globalConfigsLoading
		) {
			wasCompleteOnMount.current = isOnboardingComplete();
			hasCheckedInitialState.current = true;
		}
	}, [preferencesLoading, configsLoading, globalConfigsLoading, isOnboardingComplete]);

	// Redirect to dashboard if onboarding was already complete
	useEffect(() => {
		if (
			wasCompleteOnMount.current === true &&
			!preferencesLoading &&
			!configsLoading &&
			!globalConfigsLoading
		) {
			const timer = setTimeout(() => {
				router.push(`/dashboard/${searchSpaceId}`);
			}, 300);
			return () => clearTimeout(timer);
		}
	}, [preferencesLoading, configsLoading, globalConfigsLoading, router, searchSpaceId]);

	// Auto-configure LLM roles if global configs are available
	const autoConfigureLLMs = useCallback(async () => {
		if (hasAttemptedAutoConfig.current) return;
		if (globalConfigs.length === 0) return;
		if (isOnboardingComplete()) {
			setAutoConfigComplete(true);
			return;
		}

		hasAttemptedAutoConfig.current = true;
		setIsAutoConfiguring(true);

		try {
			const allConfigs = [...globalConfigs, ...llmConfigs];

			if (allConfigs.length === 0) {
				setIsAutoConfiguring(false);
				return;
			}

			// Use first available config for all roles
			const defaultConfigId = allConfigs[0].id;

			const newPreferences = {
				long_context_llm_id: defaultConfigId,
				fast_llm_id: defaultConfigId,
				strategic_llm_id: defaultConfigId,
			};

			
				await updatePreferences({
					search_space_id: searchSpaceId,
					data: newPreferences
				});
				await refreshPreferences();
				setAutoConfigComplete(true);
				toast.success("AI models configured automatically!", {
					description: "You can customize these in advanced settings.",
				});
		} catch (error) {
			console.error("Auto-configuration failed:", error);
		} finally {
			setIsAutoConfiguring(false);
		}
	}, [globalConfigs, llmConfigs, isOnboardingComplete, updatePreferences, refreshPreferences]);

	// Trigger auto-configuration once data is loaded
	useEffect(() => {
		if (!configsLoading && !globalConfigsLoading && !preferencesLoading) {
			autoConfigureLLMs();
		}
	}, [configsLoading, globalConfigsLoading, preferencesLoading, autoConfigureLLMs]);

	const allConfigs = [...globalConfigs, ...llmConfigs];
	const isReady = autoConfigComplete || isOnboardingComplete();

	// Loading state
	if (configsLoading || preferencesLoading || globalConfigsLoading || isAutoConfiguring) {
		return (
			<OnboardLoading
				title={isAutoConfiguring ? "Setting up your AI assistant..." : t("loading_config")}
				subtitle={
					isAutoConfiguring
						? "Auto-configuring optimal settings for you"
						: "Please wait while we load your configuration"
				}
			/>
		);
	}

	// Show LLM setup if no configs available OR if roles are not assigned yet
	// This forces users to complete role assignment before seeing the final screen
	if (allConfigs.length === 0 || !isOnboardingComplete()) {
		return (
			<OnboardLLMSetup
				searchSpaceId={searchSpaceId}
				title={t("welcome_title")}
				configTitle={
					allConfigs.length === 0 ? t("setup_llm_configuration") : t("assign_llm_roles_title")
				}
				configDescription={
					allConfigs.length === 0
						? t("configure_providers_and_assign_roles")
						: t("complete_role_assignment")
				}
				onConfigCreated={() => refreshConfigs()}
				onConfigDeleted={() => refreshConfigs()}
				onPreferencesUpdated={handleRefreshPreferences}
			/>
		);
	}

	// Main onboarding view
	return (
		<div className="min-h-screen bg-background">
			<div className="flex items-center justify-center min-h-screen p-4 md:p-8">
				<motion.div
					initial={{ opacity: 0 }}
					animate={{ opacity: 1 }}
					transition={{ duration: 0.6 }}
					className="w-full max-w-5xl"
				>
					{/* Header */}
					<OnboardHeader
						title={t("welcome_title")}
						subtitle={
							isReady ? "You're all set! Choose what you'd like to do next." : t("welcome_subtitle")
						}
						isReady={isReady}
					/>

					{/* Quick Stats */}
					<OnboardStats
						globalConfigsCount={globalConfigs.length}
						userConfigsCount={llmConfigs.length}
					/>

					{/* Action Cards */}
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						transition={{ delay: 0.6 }}
						className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10"
					>
						<OnboardActionCard
							title="Start Chatting"
							description="Jump right into the AI researcher and start asking questions"
							icon={MessageSquare}
							features={[
								"AI-powered conversations",
								"Research and explore topics",
								"Get instant insights",
							]}
							buttonText="Start Chatting"
							onClick={() => router.push(`/dashboard/${searchSpaceId}/researcher`)}
							colorScheme="violet"
							delay={0.9}
						/>

						<OnboardActionCard
							title="Add Sources"
							description="Connect your data sources to start building your knowledge base"
							icon={FileText}
							features={[
								"Connect documents and files",
								"Import from various sources",
								"Build your knowledge base",
							]}
							buttonText="Add Sources"
							onClick={() => router.push(`/dashboard/${searchSpaceId}/sources/add`)}
							colorScheme="blue"
							delay={0.8}
						/>

						<OnboardActionCard
							title="Manage Team"
							description="Invite team members and collaborate on your search space"
							icon={Users}
							features={[
								"Invite team members",
								"Assign roles & permissions",
								"Collaborate together",
							]}
							buttonText="Manage Team"
							onClick={() => router.push(`/dashboard/${searchSpaceId}/team`)}
							colorScheme="emerald"
							delay={0.7}
						/>
					</motion.div>

					{/* Advanced Settings */}
					<OnboardAdvancedSettings
						searchSpaceId={searchSpaceId}
						showLLMSettings={showAdvancedSettings}
						setShowLLMSettings={setShowAdvancedSettings}
						showPromptSettings={showPromptSettings}
						setShowPromptSettings={setShowPromptSettings}
						onConfigCreated={() => refreshConfigs()}
						onConfigDeleted={() => refreshConfigs()}
						onPreferencesUpdated={handleRefreshPreferences}
					/>

					{/* Footer */}
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						transition={{ delay: 1.1 }}
						className="text-center mt-10 text-muted-foreground text-sm"
					>
						<p>
							You can always adjust these settings later in{" "}
							<button
								type="button"
								onClick={() => router.push(`/dashboard/${searchSpaceId}/settings`)}
								className="text-primary hover:underline underline-offset-2 transition-colors"
							>
								Settings
							</button>
						</p>
					</motion.div>
				</motion.div>
			</div>
		</div>
	);
};

export default OnboardPage;
