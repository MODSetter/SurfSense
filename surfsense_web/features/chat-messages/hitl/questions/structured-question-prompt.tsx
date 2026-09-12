"use client";

import { ArrowLeftIcon, ArrowRightIcon, CornerDownLeftIcon } from "lucide-react";
import Image from "next/image";
import {
	type KeyboardEvent as ReactKeyboardEvent,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { PendingInterruptState } from "../approval";
import { usePendingInterrupt } from "../approval";
import type { StructuredQuestionAnswer, StructuredQuestionResponse } from "../types";
import {
	PREVIEW_ASSETS,
	parseStructuredQuestion,
	type StructuredQuestionData,
} from "./structured-question-contract";

export function isStructuredQuestionInterrupt(interrupt: PendingInterruptState): boolean {
	return parseStructuredQuestion(interrupt.interruptData) !== null;
}

function StructuredQuestionCard({
	pending,
	data,
}: {
	pending: PendingInterruptState;
	data: StructuredQuestionData;
}) {
	const context = usePendingInterrupt();
	const cardRef = useRef<HTMLElement>(null);
	const optionsRef = useRef<HTMLDivElement>(null);
	const [answers, setAnswers] = useState<Record<string, string[] | string>>(() =>
		Object.fromEntries(
			data.questions.map((question) => {
				if (question.input_type === "free_text") return [question.id, ""];
				const initial = question.options.find((option) => option.id === "auto");
				return [question.id, initial ? [initial.id] : []];
			})
		)
	);
	const [error, setError] = useState("");
	const [submitted, setSubmitted] = useState(false);
	const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);
	const [scrollEdges, setScrollEdges] = useState({ top: false, bottom: false });
	const activeQuestion = data.questions[activeQuestionIndex];
	const isLastQuestion = activeQuestionIndex === data.questions.length - 1;

	useEffect(() => {
		const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
		const card = cardRef.current;
		card?.focus({ preventScroll: true });
		const keepFocusInside = (event: FocusEvent) => {
			if (card && event.target instanceof Node && !card.contains(event.target)) {
				card.focus({ preventScroll: true });
			}
		};
		document.addEventListener("focusin", keepFocusInside);
		return () => {
			document.removeEventListener("focusin", keepFocusInside);
			requestAnimationFrame(() => {
				const composer =
					previous?.isConnected && !previous.hasAttribute("disabled")
						? previous
						: document.querySelector<HTMLElement>(
								".aui-composer-input-wrapper [contenteditable='true']"
							);
				composer?.focus();
			});
		};
	}, []);
	useEffect(() => {
		const handleResumeFailure = (event: Event) => {
			const detail = (event as CustomEvent).detail as { interruptIds?: unknown };
			if (
				Array.isArray(detail?.interruptIds) &&
				detail.interruptIds.includes(pending.interruptId)
			) {
				setSubmitted(false);
				setError("Could not submit this response. Please try again.");
			}
		};
		window.addEventListener("hitl-resume-failed", handleResumeFailure);
		return () => window.removeEventListener("hitl-resume-failed", handleResumeFailure);
	}, [pending.interruptId]);
	// biome-ignore lint/correctness/useExhaustiveDependencies: each question has different scroll geometry.
	useEffect(() => {
		const element = optionsRef.current;
		if (!element) {
			setScrollEdges({ top: false, bottom: false });
			return;
		}
		element.scrollTop = 0;
		const updateEdges = () => {
			const next = {
				top: element.scrollTop > 1,
				bottom: element.scrollTop + element.clientHeight < element.scrollHeight - 1,
			};
			setScrollEdges((current) =>
				current.top === next.top && current.bottom === next.bottom ? current : next
			);
		};
		updateEdges();
		const observer = new ResizeObserver(updateEdges);
		observer.observe(element);
		return () => observer.disconnect();
	}, [activeQuestion.id]);

	const validateQuestion = (question: StructuredQuestionData["questions"][number]) => {
		const answer = answers[question.id];
		const count = Array.isArray(answer) ? answer.length : String(answer ?? "").trim().length;
		if (question.required && count === 0) {
			setError(`Answer “${question.prompt}” before continuing.`);
			return false;
		}
		if (
			Array.isArray(answer) &&
			(answer.length < question.minimum_selections || answer.length > question.maximum_selections)
		) {
			setError(`Choose the requested number of options for “${question.prompt}”.`);
			return false;
		}
		setError("");
		return true;
	};

	const submit = (cancelled: boolean) => {
		if (!context || submitted || (!cancelled && !validateQuestion(activeQuestion))) return;
		const response: StructuredQuestionResponse = cancelled
			? {
					type: "cancel",
					preset_id: data.origin.preset_id,
					preset_version: data.origin.preset_version,
					tool_call_id: pending.interruptId,
				}
			: {
					type: "respond",
					preset_id: data.origin.preset_id,
					preset_version: data.origin.preset_version,
					tool_call_id: pending.interruptId,
					answers: data.questions.map<StructuredQuestionAnswer>((question) => {
						const answer = answers[question.id];
						return question.input_type === "free_text"
							? { question_id: question.id, text: String(answer ?? "").trim() }
							: {
									question_id: question.id,
									option_ids: Array.isArray(answer) ? answer : [],
								};
					}),
				};
		setError("");
		setSubmitted(true);
		context.onSubmit(pending.interruptId, [response]);
	};

	const handlePanelKeyDown = (event: ReactKeyboardEvent<HTMLElement>) => {
		if (submitted || event.nativeEvent.isComposing) return;
		if (event.key === "Escape") {
			event.preventDefault();
			submit(true);
			return;
		}
		if (["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"].includes(event.key)) {
			if (
				event.target instanceof HTMLTextAreaElement ||
				event.target instanceof HTMLButtonElement
			) {
				return;
			}
			const optionInputs = Array.from(
				optionsRef.current?.querySelectorAll<HTMLInputElement>(
					"input[type='radio'], input[type='checkbox']"
				) ?? []
			);
			if (optionInputs.length === 0) return;
			event.preventDefault();
			const focusedIndex = optionInputs.indexOf(document.activeElement as HTMLInputElement);
			const selectedIds = Array.isArray(answers[activeQuestion.id])
				? (answers[activeQuestion.id] as string[])
				: [];
			const selectedIndex = activeQuestion.options.findIndex((option) =>
				selectedIds.includes(option.id)
			);
			const currentIndex = focusedIndex >= 0 ? focusedIndex : selectedIndex;
			const direction = event.key === "ArrowDown" || event.key === "ArrowRight" ? 1 : -1;
			const nextIndex =
				currentIndex < 0
					? direction > 0
						? 0
						: optionInputs.length - 1
					: (currentIndex + direction + optionInputs.length) % optionInputs.length;
			const nextInput = optionInputs[nextIndex];
			nextInput?.focus({ preventScroll: true });
			const options = optionsRef.current;
			const option = nextInput?.closest("label");
			if (options && option) {
				const optionsBounds = options.getBoundingClientRect();
				const optionBounds = option.getBoundingClientRect();
				if (optionBounds.top < optionsBounds.top) {
					options.scrollTop -= optionsBounds.top - optionBounds.top;
				} else if (optionBounds.bottom > optionsBounds.bottom) {
					options.scrollTop += optionBounds.bottom - optionsBounds.bottom;
				}
			}
			if (activeQuestion.input_type === "single_select") {
				setAnswers((current) => ({
					...current,
					[activeQuestion.id]: [activeQuestion.options[nextIndex].id],
				}));
				setError("");
			}
			return;
		}
		if (
			event.key === "Enter" &&
			!(event.target instanceof HTMLTextAreaElement) &&
			!(event.target instanceof HTMLButtonElement)
		) {
			event.preventDefault();
			submit(false);
			return;
		}
		if (event.key !== "Tab") return;
		const focusable = Array.from(
			cardRef.current?.querySelectorAll<HTMLElement>(
				"button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
			) ?? []
		).filter((element) => !element.hasAttribute("aria-hidden"));
		if (focusable.length === 0) {
			event.preventDefault();
			cardRef.current?.focus();
			return;
		}
		const first = focusable[0];
		const last = focusable.at(-1);
		if (event.shiftKey && document.activeElement === first) {
			event.preventDefault();
			last?.focus();
		} else if (!event.shiftKey && document.activeElement === last) {
			event.preventDefault();
			first?.focus();
		}
	};

	return (
		<section
			ref={cardRef}
			tabIndex={-1}
			aria-labelledby={`structured-question-${pending.interruptId}`}
			onKeyDown={handlePanelKeyDown}
			className="overflow-hidden rounded-xl border border-border bg-muted shadow-lg outline-none"
		>
			<header className="flex items-center justify-between gap-4 px-4 py-2">
				<h2 id={`structured-question-${pending.interruptId}`} className="font-semibold text-sm">
					Questions
				</h2>
				<span className="shrink-0 text-muted-foreground text-xs tabular-nums">
					{activeQuestionIndex + 1} of {data.questions.length}
				</span>
			</header>
			<div className="px-4 pt-3">
				{data.message ? <p className="mb-2 text-muted-foreground text-xs">{data.message}</p> : null}
				<fieldset disabled={submitted} className="min-w-0">
					<legend className="mb-2 flex gap-2 font-semibold text-sm leading-5">
						<span aria-hidden="true" className="text-muted-foreground">
							{activeQuestionIndex + 1}.
						</span>
						<span>{activeQuestion.prompt}</span>
					</legend>
					{activeQuestion.input_type === "free_text" ? (
						<Textarea
							value={String(answers[activeQuestion.id] ?? "")}
							onChange={(event) =>
								setAnswers((current) => ({
									...current,
									[activeQuestion.id]: event.target.value,
								}))
							}
							maxLength={4000}
						/>
					) : (
						<div className="relative">
							<div
								ref={optionsRef}
								onScroll={() => {
									const element = optionsRef.current;
									if (!element) return;
									setScrollEdges({
										top: element.scrollTop > 1,
										bottom: element.scrollTop + element.clientHeight < element.scrollHeight - 1,
									});
								}}
								className="grid max-h-48 gap-1.5 overflow-y-auto px-1"
							>
								{activeQuestion.options.map((option, optionIndex) => {
									const selected = (answers[activeQuestion.id] as string[] | undefined)?.includes(
										option.id
									);
									return (
										<label
											key={option.id}
											className={cn(
												"relative flex min-h-11 cursor-pointer items-center gap-2.5 rounded-md border px-2.5 py-1.5 text-left transition-colors motion-reduce:transition-none",
												selected
													? "border-primary bg-primary/8 ring-1 ring-inset ring-primary/30"
													: "border-border hover:bg-muted"
											)}
										>
											<input
												type={activeQuestion.input_type === "single_select" ? "radio" : "checkbox"}
												name={`${pending.interruptId}-${activeQuestion.id}`}
												value={option.id}
												checked={selected}
												onChange={() =>
													setAnswers((current) => {
														const selectedIds = Array.isArray(current[activeQuestion.id])
															? (current[activeQuestion.id] as string[])
															: [];
														return {
															...current,
															[activeQuestion.id]:
																activeQuestion.input_type === "single_select"
																	? [option.id]
																	: selectedIds.includes(option.id)
																		? selectedIds.filter((id) => id !== option.id)
																		: [...selectedIds, option.id],
														};
													})
												}
												className="peer absolute inset-0 z-10 cursor-pointer opacity-0"
											/>
											<span
												aria-hidden="true"
												className={cn(
													"flex size-6 shrink-0 items-center justify-center rounded border font-medium text-[11px] peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2",
													selected
														? "border-primary bg-primary text-primary-foreground"
														: "border-border bg-muted text-muted-foreground"
												)}
											>
												{String.fromCharCode(65 + optionIndex)}
											</span>
											{option.preview_asset ? (
												<Image
													src={PREVIEW_ASSETS[option.preview_asset]}
													alt=""
													width={58}
													height={32}
													className="h-8 w-[3.625rem] shrink-0 rounded object-cover"
												/>
											) : null}
											<span className="min-w-0 flex-1">
												<span className="block font-medium text-sm">{option.label}</span>
												{option.description ? (
													<span className="line-clamp-1 block text-muted-foreground text-[11px]">
														{option.description}
													</span>
												) : null}
											</span>
										</label>
									);
								})}
							</div>
							{scrollEdges.top ? (
								<span
									aria-hidden="true"
									className="pointer-events-none absolute inset-x-0 top-0 z-10 h-3 bg-gradient-to-b from-muted via-muted/70 to-transparent"
								/>
							) : null}
							{scrollEdges.bottom ? (
								<span
									aria-hidden="true"
									className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-3 bg-gradient-to-t from-muted via-muted/70 to-transparent"
								/>
							) : null}
						</div>
					)}
				</fieldset>
			</div>
			<footer className="flex items-center justify-between gap-3 px-4 py-2">
				<p aria-live="polite" className="min-h-5 flex-1 text-destructive text-xs">
					{error}
				</p>
				<div className="flex shrink-0 items-center gap-2">
					<button
						type="button"
						className="px-2 py-1 font-medium text-muted-foreground text-sm transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
						disabled={submitted}
						onClick={() => submit(true)}
					>
						Skip
					</button>
					{activeQuestionIndex > 0 ? (
						<Button
							type="button"
							size="sm"
							variant="outline"
							className="gap-1.5 rounded-lg"
							disabled={submitted}
							onClick={() => {
								setError("");
								setActiveQuestionIndex((current) => current - 1);
							}}
						>
							<ArrowLeftIcon className="size-3 opacity-60" />
							Back
						</Button>
					) : null}
					<Button
						type="button"
						size="sm"
						className="gap-1.5 rounded-lg"
						disabled={submitted}
						onClick={() => {
							if (isLastQuestion) {
								submit(false);
								return;
							}
							if (validateQuestion(activeQuestion)) {
								setActiveQuestionIndex((current) => current + 1);
							}
						}}
					>
						{submitted ? "Continuing…" : isLastQuestion ? "Continue" : "Next"}
						{isLastQuestion ? (
							<CornerDownLeftIcon className="size-3 opacity-60" />
						) : (
							<ArrowRightIcon className="size-3 opacity-60" />
						)}
					</Button>
				</div>
			</footer>
		</section>
	);
}

export function StructuredQuestionPrompt() {
	const context = usePendingInterrupt();
	const prompts = useMemo(
		() =>
			(context?.pendingInterrupts ?? []).flatMap((pending) => {
				const data = parseStructuredQuestion(pending.interruptData);
				return data ? [{ pending, data }] : [];
			}),
		[context?.pendingInterrupts]
	);
	if (prompts.length === 0) return null;
	return (
		<section className="space-y-3" aria-label="Questions requiring your response">
			{prompts.map(({ pending, data }) => (
				<StructuredQuestionCard key={pending.interruptId} pending={pending} data={data} />
			))}
		</section>
	);
}
