"use client";

import { ArrowLeft, ArrowRight, Bot, CheckCircle, MessageSquare, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Logo } from "@/components/Logo";
import { CompletionStep } from "@/components/onboard/completion-step";
import { SetupLLMStep } from "@/components/onboard/setup-llm-step";
import { SetupPromptStep } from "@/components/onboard/setup-prompt-step";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useGlobalLLMConfigs, useLLMConfigs, useLLMPreferences } from "@/hooks/use-llm-configs";

const TOTAL_STEPS = 3;

const OnboardPage = () => {
	const t = useTranslations("onboard");
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	const { llmConfigs, loading: configsLoading, refreshConfigs } = useLLMConfigs(searchSpaceId);
	const { globalConfigs, loading: globalConfigsLoading } = useGlobalLLMConfigs();
	const {
		preferences,
		loading: preferencesLoading,
		isOnboardingComplete,
		refreshPreferences,
	} = useLLMPreferences(searchSpaceId);
	const [currentStep, setCurrentStep] = useState(1);
	const [hasUserProgressed, setHasUserProgressed] = useState(false);

	// Track if onboarding was complete on initial mount
	const wasCompleteOnMount = useRef<boolean | null>(null);
	const hasCheckedInitialState = useRef(false);

	// Check if user is authenticated
	useEffect(() => {
		const token = localStorage.getItem("surfsense_bearer_token");
		if (!token) {
			router.push("/login");
			return;
		}
	}, [router]);

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

	// Track if user has progressed beyond step 1
	useEffect(() => {
		if (currentStep > 1) {
			setHasUserProgressed(true);
		}
	}, [currentStep]);

	// Redirect to dashboard if onboarding was already complete on mount (not during this session)
	useEffect(() => {
		// Only redirect if:
		// 1. Onboarding was complete when page loaded
		// 2. User hasn't progressed past step 1
		// 3. All data is loaded
		if (
			wasCompleteOnMount.current === true &&
			!hasUserProgressed &&
			!preferencesLoading &&
			!configsLoading &&
			!globalConfigsLoading
		) {
			// Small delay to ensure the check is stable on initial load
			const timer = setTimeout(() => {
				router.push(`/dashboard/${searchSpaceId}`);
			}, 300);
			return () => clearTimeout(timer);
		}
	}, [
		hasUserProgressed,
		preferencesLoading,
		configsLoading,
		globalConfigsLoading,
		router,
		searchSpaceId,
	]);

	const progress = (currentStep / TOTAL_STEPS) * 100;

	const stepTitles = [t("setup_llm_configuration"), "Configure AI Responses", t("setup_complete")];

	const stepDescriptions = [
		t("configure_providers_and_assign_roles"),
		"Customize how the AI responds to your queries (Optional)",
		t("all_set"),
	];

	// User can proceed to step 2 if all roles are assigned
	const canProceedToStep2 =
		!preferencesLoading &&
		preferences.long_context_llm_id &&
		preferences.fast_llm_id &&
		preferences.strategic_llm_id;

	// User can always proceed from step 2 to step 3 (prompt config is optional)
	const canProceedToStep3 = true;

	const handleNext = () => {
		if (currentStep < TOTAL_STEPS) {
			setCurrentStep(currentStep + 1);
		}
	};

	const handlePrevious = () => {
		if (currentStep > 1) {
			setCurrentStep(currentStep - 1);
		}
	};

	if (configsLoading || preferencesLoading || globalConfigsLoading) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen">
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardContent className="flex flex-col items-center justify-center py-12">
						<Bot className="h-12 w-12 text-primary animate-pulse mb-4" />
						<p className="text-sm text-muted-foreground">{t("loading_config")}</p>
					</CardContent>
				</Card>
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20 flex items-center justify-center p-4">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
				className="w-full max-w-4xl"
			>
				{/* Header */}
				<div className="text-center mb-8">
					<div className="flex items-center justify-center mb-4">
						<Logo className="w-12 h-12 mr-3 rounded-full" />
						<h1 className="text-3xl font-bold">{t("welcome_title")}</h1>
					</div>
					<p className="text-muted-foreground text-lg">{t("welcome_subtitle")}</p>
				</div>

				{/* Progress */}
				<Card className="mb-8 bg-background/60 backdrop-blur-sm">
					<CardContent className="pt-6">
						<div className="flex items-center justify-between mb-4">
							<div className="text-sm font-medium">
								{t("step_of", { current: currentStep, total: TOTAL_STEPS })}
							</div>
							<div className="text-sm text-muted-foreground">
								{t("percent_complete", { percent: Math.round(progress) })}
							</div>
						</div>
						<Progress value={progress} className="mb-4" />
						<div className="grid grid-cols-3 gap-4">
							{Array.from({ length: TOTAL_STEPS }, (_, i) => {
								const stepNum = i + 1;
								const isCompleted = stepNum < currentStep;
								const isCurrent = stepNum === currentStep;

								return (
									<div key={stepNum} className="flex items-center space-x-2">
										<div
											className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
												isCompleted
													? "bg-primary text-primary-foreground"
													: isCurrent
														? "bg-primary/20 text-primary border-2 border-primary"
														: "bg-muted text-muted-foreground"
											}`}
										>
											{isCompleted ? <CheckCircle className="w-4 h-4" /> : stepNum}
										</div>
										<div className="flex-1 min-w-0">
											<p
												className={`text-sm font-medium truncate ${
													isCurrent ? "text-foreground" : "text-muted-foreground"
												}`}
											>
												{stepTitles[i]}
											</p>
										</div>
									</div>
								);
							})}
						</div>
					</CardContent>
				</Card>

				{/* Step Content */}
				<Card className="min-h-[500px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="text-center">
						<CardTitle className="text-2xl flex items-center justify-center gap-2">
							{currentStep === 1 && <Sparkles className="w-6 h-6" />}
							{currentStep === 2 && <MessageSquare className="w-6 h-6" />}
							{currentStep === 3 && <CheckCircle className="w-6 h-6" />}
							{stepTitles[currentStep - 1]}
						</CardTitle>
						<CardDescription className="text-base">
							{stepDescriptions[currentStep - 1]}
						</CardDescription>
					</CardHeader>
					<CardContent>
						<AnimatePresence mode="wait">
							<motion.div
								key={currentStep}
								initial={{ opacity: 0, x: 20 }}
								animate={{ opacity: 1, x: 0 }}
								exit={{ opacity: 0, x: -20 }}
								transition={{ duration: 0.3 }}
							>
								{currentStep === 1 && (
									<SetupLLMStep
										searchSpaceId={searchSpaceId}
										onConfigCreated={refreshConfigs}
										onConfigDeleted={refreshConfigs}
										onPreferencesUpdated={refreshPreferences}
									/>
								)}
								{currentStep === 2 && (
									<SetupPromptStep searchSpaceId={searchSpaceId} onComplete={handleNext} />
								)}
								{currentStep === 3 && <CompletionStep searchSpaceId={searchSpaceId} />}
							</motion.div>
						</AnimatePresence>
					</CardContent>
				</Card>

				{/* Navigation */}
				<div className="flex justify-between mt-8">
					{currentStep === 1 ? (
						<>
							<div />
							<Button
								onClick={handleNext}
								disabled={!canProceedToStep2}
								className="flex items-center gap-2"
							>
								{t("next")}
								<ArrowRight className="w-4 h-4" />
							</Button>
						</>
					) : currentStep === 2 ? (
						<>
							<Button
								variant="outline"
								onClick={handlePrevious}
								className="flex items-center gap-2"
							>
								<ArrowLeft className="w-4 h-4" />
								{t("previous")}
							</Button>
							{/* Next button is handled by SetupPromptStep component */}
							<div />
						</>
					) : (
						<>
							<Button
								variant="outline"
								onClick={handlePrevious}
								className="flex items-center gap-2"
							>
								<ArrowLeft className="w-4 h-4" />
								{t("previous")}
							</Button>
							<div />
						</>
					)}
				</div>
			</motion.div>
		</div>
	);
};

export default OnboardPage;
