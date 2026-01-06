"use client";

import { useTheme } from "next-themes";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

interface TourStep {
	target: string;
	title: string;
	content: string;
	placement: "top" | "bottom" | "left" | "right";
}

const TOUR_STEPS: TourStep[] = [
	{
		target: '[data-joyride="connector-icon"]',
		title: "Connect your data sources",
		content:
			"Connect and sync data from Gmail, Drive, Slack, Notion, Jira, Confluence, and more.",
		placement: "bottom",
	},
	{
		target: '[data-joyride="documents-sidebar"]',
		title: "Manage your documents",
		content: "Access and manage all your uploaded documents from the sidebar.",
		placement: "right",
	},
];

interface TooltipPosition {
	top: number;
	left: number;
	pointerPosition: "top" | "bottom" | "left" | "right";
}

function calculatePosition(targetEl: Element, placement: TourStep["placement"]): TooltipPosition {
	const rect = targetEl.getBoundingClientRect();
	const scrollTop = window.scrollY;
	const scrollLeft = window.scrollX;
	const tooltipWidth = 280;
	const tooltipHeight = 120;
	const offset = 16;

	let top = 0;
	let left = 0;
	let pointerPosition: TooltipPosition["pointerPosition"] = "left";

	switch (placement) {
		case "bottom":
			top = rect.bottom + scrollTop + offset;
			left = rect.left + scrollLeft + rect.width / 2 - tooltipWidth / 2;
			pointerPosition = "top";
			break;
		case "top":
			top = rect.top + scrollTop - tooltipHeight - offset;
			left = rect.left + scrollLeft + rect.width / 2 - tooltipWidth / 2;
			pointerPosition = "bottom";
			break;
		case "right":
			top = rect.top + scrollTop + rect.height / 2 - tooltipHeight / 2;
			left = rect.right + scrollLeft + offset;
			pointerPosition = "left";
			break;
		case "left":
			top = rect.top + scrollTop + rect.height / 2 - tooltipHeight / 2;
			left = rect.left + scrollLeft - tooltipWidth - offset;
			pointerPosition = "right";
			break;
	}

	// Ensure tooltip stays within viewport
	left = Math.max(10, Math.min(left, window.innerWidth - tooltipWidth - 10));
	top = Math.max(10, top);

	return { top, left, pointerPosition };
}

function Spotlight({
	targetEl,
	isDarkMode,
	currentStepTarget,
}: {
	targetEl: Element;
	isDarkMode: boolean;
	currentStepTarget: string;
}) {
	const rect = targetEl.getBoundingClientRect();
	const padding = 6;
	const shadowColor = isDarkMode ? "#172554" : "#0c1a3a";

	// Check if this is the connector icon step - verify both the selector matches AND the element matches
	// This prevents the shape from changing before targetEl updates
	const isConnectorSelector = currentStepTarget === '[data-joyride="connector-icon"]';
	const isConnectorElement = targetEl.matches('[data-joyride="connector-icon"]');
	const isConnectorStep = isConnectorSelector && isConnectorElement;

	// For circle, use the larger dimension to ensure it's a perfect circle
	const circleSize = isConnectorStep ? Math.max(rect.width, rect.height) : 0;
	const circleTop = isConnectorStep ? rect.top + (rect.height - circleSize) / 2 : rect.top;
	const circleLeft = isConnectorStep ? rect.left + (rect.width - circleSize) / 2 : rect.left;

	return (
		<>
			{/* Dark overlay with cutout using box-shadow technique */}
			<div
				className="fixed pointer-events-none"
				style={{
					top: isConnectorStep ? circleTop - padding : rect.top - padding,
					left: isConnectorStep ? circleLeft - padding : rect.left - padding,
					width: isConnectorStep ? circleSize + padding * 2 : rect.width + padding * 2,
					height: isConnectorStep ? circleSize + padding * 2 : rect.height + padding * 2,
					borderRadius: isConnectorStep ? "50%" : 8,
					boxShadow: `0 0 0 9999px rgba(0, 0, 0, 0.6)`,
					backgroundColor: "transparent",
					zIndex: 99996,
				}}
			/>
			{/* Blue shadow behind the button - starts from button border */}
			<div
				className="fixed pointer-events-none"
				style={{
					top: isConnectorStep ? circleTop : rect.top,
					left: isConnectorStep ? circleLeft : rect.left,
					width: isConnectorStep ? circleSize : rect.width,
					height: isConnectorStep ? circleSize : rect.height,
					borderRadius: isConnectorStep ? "50%" : 8,
					boxShadow: `0 0 10px 2px ${shadowColor}CC, 0 0 20px 6px ${shadowColor}99, 0 0 40px 12px ${shadowColor}66`,
					backgroundColor: "transparent",
					zIndex: 99997,
				}}
			/>
		</>
	);
}

function TourTooltip({
	step,
	stepIndex,
	totalSteps,
	position,
	onNext,
	onPrev,
	onSkip,
	isDarkMode,
}: {
	step: TourStep;
	stepIndex: number;
	totalSteps: number;
	position: TooltipPosition;
	targetRect: DOMRect;
	onNext: () => void;
	onPrev: () => void;
	onSkip: () => void;
	isDarkMode: boolean;
}) {
	const isLastStep = stepIndex === totalSteps - 1;
	const isFirstStep = stepIndex === 0;

	const bgColor = isDarkMode ? "#18181b" : "#18181b"; // Dark tooltip for both modes as shown in image
	const textColor = "#ffffff";
	const mutedTextColor = "#a1a1aa";

	// Calculate pointer line position
	const getPointerStyles = (): React.CSSProperties => {
		const lineLength = 16;
		const dotSize = 6;
		// Check if this is the documents step (stepIndex === 1)
		const isDocumentsStep = stepIndex === 1;

		if (position.pointerPosition === "left") {
			return {
				position: "absolute",
				left: -lineLength - dotSize,
				top: isDocumentsStep ? "calc(50% - 8px)" : "50%",
				transform: "translateY(-50%)",
				display: "flex",
				alignItems: "center",
			};
		}
		if (position.pointerPosition === "top") {
			return {
				position: "absolute",
				top: -lineLength - dotSize,
				left: "50%",
				transform: "translateX(-50%)",
				display: "flex",
				flexDirection: "column",
				alignItems: "center",
			};
		}
		return {};
	};

	const renderPointer = () => {
		const lineColor = "#18181B";

		if (position.pointerPosition === "left") {
			return (
				<div style={getPointerStyles()}>
					<div
						style={{
							width: 6,
							height: 6,
							borderRadius: "50%",
							backgroundColor: lineColor,
						}}
					/>
					<div
						style={{
							width: 16,
							height: 2,
							backgroundColor: lineColor,
						}}
					/>
				</div>
			);
		}
		if (position.pointerPosition === "top") {
			return (
				<div style={getPointerStyles()}>
					<div
						style={{
							width: 6,
							height: 6,
							borderRadius: "50%",
							backgroundColor: lineColor,
						}}
					/>
					<div
						style={{
							width: 2,
							height: 16,
							backgroundColor: lineColor,
						}}
					/>
				</div>
			);
		}
		return null;
	};

	// Render step dots
	const renderStepDots = () => {
		return (
			<div className="flex items-center gap-1.5">
				{Array.from({ length: totalSteps }).map((_, i) => (
					<div
						key={TOUR_STEPS[i]?.target ?? `step-${i}`}
						style={{
							width: 6,
							height: 6,
							borderRadius: "50%",
							backgroundColor: i === stepIndex ? "#ffffff" : "#52525b",
							transition: "background-color 0.2s",
						}}
					/>
				))}
			</div>
		);
	};

	return (
		<div
			role="dialog"
			aria-modal="true"
			aria-labelledby="tour-title"
			className="fixed z-[99999]"
			style={{
				top: position.top,
				left: position.left,
				width: 280,
			}}
			onClick={(e) => e.stopPropagation()}
			onKeyDown={(e) => e.stopPropagation()}
		>
			{/* Pointer line */}
			{renderPointer()}

			<div
				className="relative rounded-lg p-4"
				style={{
					backgroundColor: bgColor,
					color: textColor,
					boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
				}}
			>
				{/* Content */}
				<div>
					<h3 id="tour-title" className="text-sm font-semibold mb-1.5" style={{ color: textColor }}>
						{step.title}
					</h3>
					<p className="text-sm leading-relaxed" style={{ color: mutedTextColor }}>
						{step.content}
					</p>
				</div>

				{/* Footer */}
				<div className="flex items-center justify-between mt-4">
					{/* Step dots */}
					{renderStepDots()}

					{/* Navigation buttons */}
					<div className="flex items-center gap-3">
						{!isFirstStep && (
							<button
								type="button"
								onClick={(e) => {
									e.stopPropagation();
									onPrev();
								}}
								className="text-sm font-medium transition-opacity hover:opacity-80"
								style={{ color: mutedTextColor }}
							>
								Back
							</button>
						)}
						{isFirstStep && (
							<button
								type="button"
								onClick={(e) => {
									e.stopPropagation();
									onSkip();
								}}
								className="text-sm font-medium transition-opacity hover:opacity-80"
								style={{ color: mutedTextColor }}
							>
								Skip
							</button>
						)}
						<button
							type="button"
							onClick={(e) => {
								e.stopPropagation();
								onNext();
							}}
							className="text-sm font-medium transition-opacity hover:opacity-80"
							style={{ color: textColor }}
						>
							{isLastStep ? "Done" : "Next"}
						</button>
					</div>
				</div>
			</div>
		</div>
	);
}

export function OnboardingTour() {
	const [isActive, setIsActive] = useState(false);
	const [stepIndex, setStepIndex] = useState(0);
	const [targetEl, setTargetEl] = useState<Element | null>(null);
	const [position, setPosition] = useState<TooltipPosition | null>(null);
	const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
	const [mounted, setMounted] = useState(false);
	const { resolvedTheme } = useTheme();
	const retryCountRef = useRef(0);
	const maxRetries = 10;

	const isDarkMode = resolvedTheme === "dark";
	const currentStep = TOUR_STEPS[stepIndex];

	// Handle mounting for portal
	useEffect(() => {
		setMounted(true);
	}, []);

	// Find and track target element with retry logic
	const updateTarget = useCallback(() => {
		if (!currentStep) return;

		const el = document.querySelector(currentStep.target);
		if (el) {
			setTargetEl(el);
			setTargetRect(el.getBoundingClientRect());
			setPosition(calculatePosition(el, currentStep.placement));
			retryCountRef.current = 0;
		} else if (retryCountRef.current < maxRetries) {
			retryCountRef.current++;
			setTimeout(() => {
				const retryEl = document.querySelector(currentStep.target);
				if (retryEl) {
					setTargetEl(retryEl);
					setTargetRect(retryEl.getBoundingClientRect());
					setPosition(calculatePosition(retryEl, currentStep.placement));
					retryCountRef.current = 0;
				}
			}, 200);
		}
	}, [currentStep]);

	// Start tour and find first target
	useEffect(() => {
		const timer = setTimeout(() => {
			const el = document.querySelector(TOUR_STEPS[0].target);
			if (el) {
				setIsActive(true);
				setTargetEl(el);
				setTargetRect(el.getBoundingClientRect());
				setPosition(calculatePosition(el, TOUR_STEPS[0].placement));
			}
		}, 1000);

		return () => clearTimeout(timer);
	}, []);

	// Update position on resize/scroll
	useEffect(() => {
		if (!isActive || !targetEl) return;

		const handleUpdate = () => {
			const rect = targetEl.getBoundingClientRect();
			if (rect.width > 0 && rect.height > 0) {
				setTargetRect(rect);
				setPosition(calculatePosition(targetEl, currentStep?.placement || "bottom"));
			}
		};

		window.addEventListener("resize", handleUpdate);
		window.addEventListener("scroll", handleUpdate, true);

		return () => {
			window.removeEventListener("resize", handleUpdate);
			window.removeEventListener("scroll", handleUpdate, true);
		};
	}, [isActive, targetEl, currentStep?.placement]);

	// Update target when step changes
	useEffect(() => {
		if (isActive && currentStep) {
			// Try to find element synchronously first to prevent any delay
			const el = document.querySelector(currentStep.target);
			if (el) {
				// Found immediately - update state synchronously to prevent flicker
				const rect = el.getBoundingClientRect();
				const newPosition = calculatePosition(el, currentStep.placement);
				// React 18+ automatically batches these updates
				setTargetEl(el);
				setTargetRect(rect);
				setPosition(newPosition);
				retryCountRef.current = 0;
			} else {
				// Not found immediately, use updateTarget with retry logic
				// Use requestAnimationFrame to batch with next paint
				const frameId = requestAnimationFrame(() => {
					updateTarget();
				});
				return () => cancelAnimationFrame(frameId);
			}
		}
	}, [isActive, updateTarget, currentStep]);

	// Ensure target element is above overlay layers so content is fully visible
	useEffect(() => {
		if (!targetEl || !isActive) return;

		const originalZIndex = (targetEl as HTMLElement).style.zIndex;
		const originalPosition = (targetEl as HTMLElement).style.position;

		// Ensure the element has a position that allows z-index
		if (getComputedStyle(targetEl).position === "static") {
			(targetEl as HTMLElement).style.position = "relative";
		}
		(targetEl as HTMLElement).style.zIndex = "99999";

		return () => {
			(targetEl as HTMLElement).style.zIndex = originalZIndex;
			if (originalPosition) {
				(targetEl as HTMLElement).style.position = originalPosition;
			} else if (getComputedStyle(targetEl).position === "relative" && originalPosition === "") {
				(targetEl as HTMLElement).style.position = "";
			}
		};
	}, [targetEl, isActive]);

	const handleNext = useCallback(() => {
		if (stepIndex < TOUR_STEPS.length - 1) {
			retryCountRef.current = 0;
			setStepIndex(stepIndex + 1);
		} else {
			setIsActive(false);
		}
	}, [stepIndex]);

	const handlePrev = useCallback(() => {
		if (stepIndex > 0) {
			retryCountRef.current = 0;
			setStepIndex(stepIndex - 1);
		}
	}, [stepIndex]);

	const handleSkip = useCallback(() => {
		setIsActive(false);
	}, []);

	// Handle overlay click to close
	const handleOverlayClick = useCallback(() => {
		setIsActive(false);
	}, []);

	// Handle escape key
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape" && isActive) {
				setIsActive(false);
			}
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [isActive]);

	// Don't render if not active or not mounted
	if (!mounted || !isActive) {
		return null;
	}

	return createPortal(
		<div className="fixed inset-0 z-[99995]">
			{/* Clickable backdrop to close */}
			<button
				type="button"
				className="fixed inset-0 w-full h-full bg-transparent border-0 cursor-default"
				onClick={handleOverlayClick}
				aria-label="Close tour"
			/>
			{/* Only render Spotlight and TourTooltip when we have target data */}
			{targetEl && position && currentStep && targetRect && (
				<>
					<Spotlight targetEl={targetEl} isDarkMode={isDarkMode} currentStepTarget={currentStep.target} />
					<TourTooltip
						step={currentStep}
						stepIndex={stepIndex}
						totalSteps={TOUR_STEPS.length}
						position={position}
						targetRect={targetRect}
						onNext={handleNext}
						onPrev={handlePrev}
						onSkip={handleSkip}
						isDarkMode={isDarkMode}
					/>
				</>
			)}
		</div>,
		document.body
	);
}
