"use client";

import { useAtomValue } from "jotai";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
	createNewLLMConfigMutationAtom,
	updateLLMPreferencesMutationAtom,
} from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { Logo } from "@/components/Logo";
import { LLMConfigForm, type LLMConfigFormData } from "@/components/shared/llm-config-form";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { getBearerToken, redirectToLogin } from "@/lib/auth-utils";

export default function OnboardPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);
	// Queries
	const {
		data: globalConfigs = [],
		isFetching: globalConfigsLoading,
		isSuccess: globalConfigsLoaded,
	} = useAtomValue(globalNewLLMConfigsAtom);
	const { data: preferences = {}, isFetching: preferencesLoading } =
		useAtomValue(llmPreferencesAtom);

	// Mutations
	const { mutateAsync: createConfig, isPending: isCreating } = useAtomValue(
		createNewLLMConfigMutationAtom
	);
	const { mutateAsync: updatePreferences, isPending: isUpdatingPreferences } = useAtomValue(
		updateLLMPreferencesMutationAtom
	);

	// State
	const [isAutoConfiguring, setIsAutoConfiguring] = useState(false);
	const hasAttemptedAutoConfig = useRef(false);

	// Check authentication
	useEffect(() => {
		const token = getBearerToken();
		if (!token) {
			redirectToLogin();
		}
	}, []);

	// Check if onboarding is already complete (including 0 for Auto mode)
	const isOnboardingComplete =
		preferences.agent_llm_id !== null &&
		preferences.agent_llm_id !== undefined &&
		preferences.document_summary_llm_id !== null &&
		preferences.document_summary_llm_id !== undefined;

	useEffect(() => {
		if (!preferencesLoading && isOnboardingComplete) {
			router.push(`/dashboard/${searchSpaceId}/new-chat`);
		}
	}, [preferencesLoading, isOnboardingComplete, router, searchSpaceId]);

	useEffect(() => {
		const autoConfigureWithGlobal = async () => {
			if (hasAttemptedAutoConfig.current) return;
			if (globalConfigsLoading || preferencesLoading) return;
			if (!globalConfigsLoaded) return;
			if (isOnboardingComplete) return;

			if (globalConfigs.length > 0) {
				hasAttemptedAutoConfig.current = true;
				setIsAutoConfiguring(true);

				try {
					const firstGlobalConfig = globalConfigs[0];

					await updatePreferences({
						search_space_id: searchSpaceId,
						data: {
							agent_llm_id: firstGlobalConfig.id,
							document_summary_llm_id: firstGlobalConfig.id,
						},
					});

					toast.success("AI configured automatically!", {
						description: `Using ${firstGlobalConfig.name}. You can customize this later in Settings.`,
					});

					router.push(`/dashboard/${searchSpaceId}/new-chat`);
				} catch (error) {
					console.error("Auto-configuration failed:", error);
					toast.error("Auto-configuration failed. Please add a configuration manually.");
					setIsAutoConfiguring(false);
				}
			}
		};

		autoConfigureWithGlobal();
	}, [
		globalConfigs,
		globalConfigsLoading,
		globalConfigsLoaded,
		preferencesLoading,
		isOnboardingComplete,
		updatePreferences,
		searchSpaceId,
		router,
	]);

	const handleSubmit = async (formData: LLMConfigFormData) => {
		try {
			const newConfig = await createConfig(formData);

			await updatePreferences({
				search_space_id: searchSpaceId,
				data: {
					agent_llm_id: newConfig.id,
					document_summary_llm_id: newConfig.id,
				},
			});

			toast.success("Configuration created!", {
				description: "Redirecting to chat...",
			});

			router.push(`/dashboard/${searchSpaceId}/new-chat`);
		} catch (error) {
			console.error("Failed to create config:", error);
			if (error instanceof Error) {
				toast.error(error.message || "Failed to create configuration");
			}
		}
	};

	const isSubmitting = isCreating || isUpdatingPreferences;

	const isLoading = globalConfigsLoading || preferencesLoading || isAutoConfiguring;
	useGlobalLoadingEffect(isLoading);

	if (isLoading) {
		return null;
	}

	if (globalConfigs.length > 0 && !isAutoConfiguring) {
		return null;
	}

	return (
		<div className="h-screen flex flex-col items-center p-4 bg-background dark:bg-neutral-900 select-none overflow-hidden">
			<div className="w-full max-w-lg flex flex-col min-h-0 h-full gap-6 py-8">
				{/* Header */}
				<div className="text-center space-y-3 shrink-0">
					<Logo className="w-12 h-12 mx-auto" />
					<div className="space-y-1">
						<h1 className="text-2xl font-semibold tracking-tight">Configure Your AI</h1>
						<p className="text-sm text-muted-foreground">
							Add your LLM provider to get started with SurfSense
						</p>
					</div>
				</div>

				{/* Form card */}
				<div className="rounded-xl border bg-background dark:bg-neutral-900 flex-1 min-h-0 overflow-y-auto px-6 py-6">
					<LLMConfigForm
						searchSpaceId={searchSpaceId}
						onSubmit={handleSubmit}
						mode="create"
						showAdvanced={true}
						formId="onboard-config-form"
						initialData={{
							citations_enabled: true,
							use_default_system_instructions: true,
						}}
					/>
				</div>

				{/* Footer */}
				<div className="text-center space-y-4 shrink-0">
					<Button
						type="submit"
						form="onboard-config-form"
						disabled={isSubmitting}
						className="relative text-sm h-9 min-w-[180px]"
					>
						<span className={isSubmitting ? "opacity-0" : ""}>Start Using SurfSense</span>
						{isSubmitting && <Spinner size="sm" className="absolute" />}
					</Button>
					<p className="text-xs text-muted-foreground">You can add more configurations later</p>
				</div>
			</div>
		</div>
	);
}
