"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { fetchThreads } from "@/lib/chat/thread-persistence";

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
		content: "Connect and sync data from Gmail, Drive, Slack, Notion, Jira, Confluence, and more.",
		placement: "bottom",
	},
	{
		target: '[data-joyride="documents-sidebar"]',
		title: "Manage your documents",
		content: "Access and manage all your uploaded documents.",
		placement: "right",
	},
	{
		target: '[data-joyride="inbox-sidebar"]',
		title: "Check your inbox",
		content: "View mentions and notifications in one place.",
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
	const shadowColor = isDarkMode ? "#172554" : "#3b82f6";

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
					boxShadow: isDarkMode
						? `0 0 0 9999px rgba(0, 0, 0, 0.6)`
						: `0 0 0 9999px rgba(0, 0, 0, 0.3)`,
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
					boxShadow: isDarkMode
						? `0 0 10px 2px ${shadowColor}CC, 0 0 20px 6px ${shadowColor}99, 0 0 40px 12px ${shadowColor}66`
						: `0 0 6px 1px ${shadowColor}80, 0 0 12px 3px ${shadowColor}50, 0 0 20px 6px ${shadowColor}30`,
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
	const [contentKey, setContentKey] = useState(stepIndex);
	const [shouldAnimate, setShouldAnimate] = useState(false);
	const prevStepIndexRef = useRef(stepIndex);
	const isLastStep = stepIndex === totalSteps - 1;
	const isFirstStep = stepIndex === 0;

	// Update content key when step changes to trigger animation
	// Only animate if stepIndex actually changes (not on initial mount)
	useEffect(() => {
		if (prevStepIndexRef.current !== stepIndex) {
			setShouldAnimate(true);
			setContentKey(stepIndex);
			prevStepIndexRef.current = stepIndex;
		}
	}, [stepIndex]);

	const bgColor = isDarkMode ? "#18181b" : "#ffffff";
	const textColor = isDarkMode ? "#ffffff" : "#18181b";
	const mutedTextColor = isDarkMode ? "#a1a1aa" : "#71717a";

	// Calculate pointer line position
	const getPointerStyles = (): React.CSSProperties => {
		const lineLength = 16;
		const dotSize = 6;
		// Check if this is the documents step (stepIndex === 1) or inbox step (stepIndex === 2)
		const isDocumentsStep = stepIndex === 1;
		const isInboxStep = stepIndex === 2;

		if (position.pointerPosition === "left") {
			return {
				position: "absolute",
				left: -lineLength - dotSize,
				top: isDocumentsStep || isInboxStep ? "calc(50% - 8px)" : "50%",
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
		const lineColor = isDarkMode ? "#18181B" : "#ffffff";

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
							backgroundColor:
								i === stepIndex
									? isDarkMode
										? "#ffffff"
										: "#18181b"
									: isDarkMode
										? "#52525b"
										: "#d4d4d8",
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
				transition: "top 0.4s cubic-bezier(0.4, 0, 0.2, 1), left 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
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
					boxShadow: isDarkMode
						? "0 25px 50px -12px rgba(0, 0, 0, 0.5)"
						: "0 25px 50px -12px rgba(0, 0, 0, 0.15)",
				}}
			>
				{/* Content */}
				<div
					key={contentKey}
					style={{
						animation: shouldAnimate ? "fadeInSlide 0.3s ease-out" : "none",
					}}
					onAnimationEnd={() => setShouldAnimate(false)}
				>
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
	const [spotlightTargetEl, setSpotlightTargetEl] = useState<Element | null>(null);
	const [spotlightStepTarget, setSpotlightStepTarget] = useState<string | null>(null);
	const [position, setPosition] = useState<TooltipPosition | null>(null);
	const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
	const [mounted, setMounted] = useState(false);
	const { resolvedTheme } = useTheme();
	const pathname = usePathname();
	const retryCountRef = useRef(0);
	const maxRetries = 10;
	// Track previous user ID to detect user changes
	const previousUserIdRef = useRef<string | null>(null);

	// Get user data
	const { data: user } = useAtomValue(currentUserAtom);
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);

	// Fetch threads data
	const { data: threadsData } = useQuery({
		queryKey: ["threads", searchSpaceId, { limit: 1 }],
		queryFn: () => fetchThreads(Number(searchSpaceId), 1), // Only need to check if any exist
		enabled: !!searchSpaceId,
	});

	// Get document type counts
	const { data: documentTypeCounts } = useAtomValue(documentTypeCountsAtom);

	// Get connectors
	const { data: connectors = [] } = useAtomValue(connectorsAtom);

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

	// Check if tour should run: localStorage + data validation with user ID tracking
	useEffect(() => {
		// Don't check if not mounted or no user
		if (!mounted || !user?.id || !searchSpaceId) return;

		// Check if on new-chat page
		const isNewChatPage = pathname?.includes("/new-chat");
		if (!isNewChatPage) return;

		// Wait for all data to be loaded before making decision
		// Data is considered loaded when:
		// - threadsData is defined (query completed, even if empty)
		// - documentTypeCounts is defined (query completed, even if empty object)
		// - connectors is an array (always defined with default [])
		// If searchSpaceId is not set, connectors query won't run, but that's okay
		const dataLoaded = threadsData !== undefined && documentTypeCounts !== undefined;
		if (!dataLoaded) return;

		const currentUserId = user.id;
		const previousUserId = previousUserIdRef.current;

		// Detect user change - if user ID changed, reset tour state
		if (previousUserId !== null && previousUserId !== currentUserId) {
			// User changed - reset tour state and re-evaluate for new user
			setIsActive(false);
			setStepIndex(0);
			setTargetEl(null);
			setSpotlightTargetEl(null);
			setSpotlightStepTarget(null);
			setPosition(null);
			setTargetRect(null);
			retryCountRef.current = 0;
		}

		// Update previous user ID ref
		previousUserIdRef.current = currentUserId;

		// Check localStorage for CURRENT user ID (not stale cache)
		// This ensures we check the correct user's tour status
		const tourKey = `surfsense-tour-${currentUserId}`;
		const hasSeenTour = localStorage.getItem(tourKey);
		if (hasSeenTour === "true") {
			return; // Current user has seen tour, don't show
		}

		// Validate user is actually new (reliable check)
		const threads = threadsData?.threads ?? [];
		const hasThreads = threads.length > 0;

		// Check document counts - sum all document type counts
		const totalDocuments = documentTypeCounts
			? Object.values(documentTypeCounts).reduce((sum, count) => sum + count, 0)
			: 0;
		const hasDocuments = totalDocuments > 0;

		const hasConnectors = connectors.length > 0;

		// User is new if they have no threads, documents, or connectors
		const isNewUser = !hasThreads && !hasDocuments && !hasConnectors;

		// Only show tour if user is new and hasn't seen it
		// Don't auto-mark as seen if user has data - let them explicitly dismiss it
		if (!isNewUser) {
			return; // User has data, don't show tour
		}

		// User is new and hasn't seen tour - wait for DOM elements and start tour
		const checkAndStartTour = () => {
			// Check if all required elements exist
			const connectorEl = document.querySelector(TOUR_STEPS[0].target);
			const documentsEl = document.querySelector(TOUR_STEPS[1].target);
			const inboxEl = document.querySelector(TOUR_STEPS[2].target);

			if (connectorEl && documentsEl && inboxEl) {
				// All elements found, start tour
				setIsActive(true);
				setTargetEl(connectorEl);
				setSpotlightTargetEl(connectorEl);
				setSpotlightStepTarget(TOUR_STEPS[0].target);
				setTargetRect(connectorEl.getBoundingClientRect());
				setPosition(calculatePosition(connectorEl, TOUR_STEPS[0].placement));
			} else {
				// Retry after delay
				setTimeout(checkAndStartTour, 200);
			}
		};

		// Start checking after initial delay
		const timer = setTimeout(checkAndStartTour, 500);
		return () => clearTimeout(timer);
	}, [mounted, user?.id, searchSpaceId, pathname, threadsData, documentTypeCounts, connectors]);

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

	// Delay spotlight update to sync with tooltip animation
	useEffect(() => {
		if (targetEl && currentStep) {
			const timer = setTimeout(() => {
				setSpotlightTargetEl(targetEl);
				setSpotlightStepTarget(currentStep.target);
			}, 100);
			return () => clearTimeout(timer);
		}
	}, [targetEl, currentStep]);

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
			// Tour completed - save to localStorage
			if (user?.id) {
				const tourKey = `surfsense-tour-${user.id}`;
				localStorage.setItem(tourKey, "true");
			}
			setIsActive(false);
		}
	}, [stepIndex, user?.id]);

	const handlePrev = useCallback(() => {
		if (stepIndex > 0) {
			retryCountRef.current = 0;
			setStepIndex(stepIndex - 1);
		}
	}, [stepIndex]);

	const handleSkip = useCallback(() => {
		// Tour skipped - save to localStorage
		if (user?.id) {
			const tourKey = `surfsense-tour-${user.id}`;
			localStorage.setItem(tourKey, "true");
		}
		setIsActive(false);
	}, [user?.id]);

	// Handle overlay click to close
	const handleOverlayClick = useCallback(() => {
		// Tour closed - save to localStorage
		if (user?.id) {
			const tourKey = `surfsense-tour-${user.id}`;
			localStorage.setItem(tourKey, "true");
		}
		setIsActive(false);
	}, [user?.id]);

	// Handle escape key
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape" && isActive) {
				// Tour closed via escape - save to localStorage
				if (user?.id) {
					const tourKey = `surfsense-tour-${user.id}`;
					localStorage.setItem(tourKey, "true");
				}
				setIsActive(false);
			}
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [isActive, user?.id]);

	// Don't render if not active or not mounted
	if (!mounted || !isActive) {
		return null;
	}

	return createPortal(
		<>
			<style>{`
				@keyframes fadeInSlide {
					from {
						opacity: 0;
						transform: translateY(8px);
					}
					to {
						opacity: 1;
						transform: translateY(0);
					}
				}
				@keyframes fadeIn {
					from {
						opacity: 0;
					}
					to {
						opacity: 1;
					}
				}
			`}</style>
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
						{spotlightTargetEl && spotlightStepTarget && (
							<Spotlight
								targetEl={spotlightTargetEl}
								isDarkMode={isDarkMode}
								currentStepTarget={spotlightStepTarget}
							/>
						)}
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
			</div>
		</>,
		document.body
	);
}
