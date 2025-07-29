"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Bot, CheckCircle, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { AddProviderStep } from "@/components/onboard/add-provider-step";
import { AssignRolesStep } from "@/components/onboard/assign-roles-step";
import { CompletionStep } from "@/components/onboard/completion-step";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useLLMConfigs, useLLMPreferences } from "@/hooks/use-llm-configs";

const TOTAL_STEPS = 3;

const OnboardPage = () => {
	const router = useRouter();
	const { llmConfigs, loading: configsLoading, refreshConfigs } = useLLMConfigs();
	const {
		preferences,
		loading: preferencesLoading,
		isOnboardingComplete,
		refreshPreferences,
	} = useLLMPreferences();
	const [currentStep, setCurrentStep] = useState(1);
	const [hasUserProgressed, setHasUserProgressed] = useState(false);

	// Check if user is authenticated
	useEffect(() => {
		const token = localStorage.getItem("surfsense_bearer_token");
		if (!token) {
			router.push("/login");
			return;
		}
	}, [router]);

	// Track if user has progressed beyond step 1
	useEffect(() => {
		if (currentStep > 1) {
			setHasUserProgressed(true);
		}
	}, [currentStep]);

	// Redirect to dashboard if onboarding is already complete and user hasn't progressed (fresh page load)
	useEffect(() => {
		if (!preferencesLoading && isOnboardingComplete() && !hasUserProgressed) {
			router.push("/dashboard");
		}
	}, [preferencesLoading, isOnboardingComplete, hasUserProgressed, router]);

	const progress = (currentStep / TOTAL_STEPS) * 100;

	const stepTitles = ["Add LLM Provider", "Assign LLM Roles", "Setup Complete"];

	const stepDescriptions = [
		"Configure your first model provider",
		"Assign specific roles to your LLM configurations",
		"You're all set to start using SurfSense!",
	];

	const canProceedToStep2 = !configsLoading && llmConfigs.length > 0;
	const canProceedToStep3 =
		!preferencesLoading &&
		preferences.long_context_llm_id &&
		preferences.fast_llm_id &&
		preferences.strategic_llm_id;

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

	const handleComplete = () => {
		router.push("/dashboard");
	};

	if (configsLoading || preferencesLoading) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen">
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardContent className="flex flex-col items-center justify-center py-12">
						<Bot className="h-12 w-12 text-primary animate-pulse mb-4" />
						<p className="text-sm text-muted-foreground">Loading your configuration...</p>
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
						<Logo className="w-12 h-12 mr-3" />
						<h1 className="text-3xl font-bold">Welcome to SurfSense</h1>
					</div>
					<p className="text-muted-foreground text-lg">
						Let's configure your SurfSense to get started
					</p>
				</div>

				{/* Progress */}
				<Card className="mb-8 bg-background/60 backdrop-blur-sm">
					<CardContent className="pt-6">
						<div className="flex items-center justify-between mb-4">
							<div className="text-sm font-medium">
								Step {currentStep} of {TOTAL_STEPS}
							</div>
							<div className="text-sm text-muted-foreground">{Math.round(progress)}% Complete</div>
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
							{currentStep === 1 && <Bot className="w-6 h-6" />}
							{currentStep === 2 && <Sparkles className="w-6 h-6" />}
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
									<AddProviderStep
										onConfigCreated={refreshConfigs}
										onConfigDeleted={refreshConfigs}
									/>
								)}
								{currentStep === 2 && <AssignRolesStep onPreferencesUpdated={refreshPreferences} />}
								{currentStep === 3 && <CompletionStep />}
							</motion.div>
						</AnimatePresence>
					</CardContent>
				</Card>

				{/* Navigation */}
				<div className="flex justify-between mt-8">
					<Button
						variant="outline"
						onClick={handlePrevious}
						disabled={currentStep === 1}
						className="flex items-center gap-2"
					>
						<ArrowLeft className="w-4 h-4" />
						Previous
					</Button>

					<div className="flex gap-2">
						{currentStep < TOTAL_STEPS && (
							<Button
								onClick={handleNext}
								disabled={
									(currentStep === 1 && !canProceedToStep2) ||
									(currentStep === 2 && !canProceedToStep3)
								}
								className="flex items-center gap-2"
							>
								Next
								<ArrowRight className="w-4 h-4" />
							</Button>
						)}

						{currentStep === TOTAL_STEPS && (
							<Button onClick={handleComplete} className="flex items-center gap-2">
								Complete Setup
								<CheckCircle className="w-4 h-4" />
							</Button>
						)}
					</div>
				</div>
			</motion.div>
		</div>
	);
};

export default OnboardPage;
