"use client";

import { ArrowLeft, ArrowRight, Check, Lightbulb, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { StudyText } from "../study-text/study-text";
import type { Quiz } from "./schema";
import type { QuizState } from "./state";

const LABELS = ["A", "B", "C", "D"] as const;

export function ReviewScreen({
	quiz,
	state,
	index,
	onIndexChange,
	onExit,
}: {
	quiz: Quiz;
	state: QuizState;
	index: number;
	onIndexChange: (index: number) => void;
	onExit: () => void;
}) {
	const question = quiz.questions[index];
	const selected = state.answers[String(index)];
	const headingRef = useRef<HTMLHeadingElement>(null);
	useEffect(() => headingRef.current?.focus(), []);
	const moveTo = (nextIndex: number) => {
		onIndexChange(nextIndex);
		requestAnimationFrame(() => headingRef.current?.focus());
	};

	return (
		<section>
			<div className="mb-6 flex items-center justify-between gap-3">
				<div>
					<p className="text-sm text-muted-foreground">Review</p>
					<p className="font-medium">
						Question {index + 1} of {quiz.questions.length}
					</p>
				</div>
				<Button
					type="button"
					variant="outline"
					size="sm"
					onClick={onExit}
					className="border-0 bg-white text-black hover:bg-white/90 hover:text-black dark:bg-white dark:text-black dark:hover:bg-white/90 dark:hover:text-black"
				>
					Exit review
				</Button>
			</div>
			<h2
				ref={headingRef}
				tabIndex={-1}
				className="mb-6 text-xl font-semibold outline-none sm:text-2xl"
			>
				<StudyText content={question.question_text} />
			</h2>
			<div className="space-y-3">
				{question.options.map((option, optionIndex) => {
					const correct = optionIndex === question.correct_option_index;
					const chosen = optionIndex === selected;
					return (
						<div
							key={option}
							className={cn(
								"flex min-h-14 items-center gap-3 rounded-xl border p-4",
								correct
									? "border-primary bg-primary/5"
									: chosen
										? "border-destructive bg-destructive/5"
										: "border-border"
							)}
						>
							<span className="font-medium text-muted-foreground">{LABELS[optionIndex]}.</span>
							<span className="min-w-0 flex-1">
								<StudyText content={option} />
							</span>
							{correct ? (
								<span className="text-green-600 dark:text-green-400">
									<Check aria-hidden="true" className="size-5" />
									<span className="sr-only">Correct answer</span>
								</span>
							) : chosen ? (
								<span className="text-red-600 dark:text-red-400">
									<X aria-hidden="true" className="size-5" />
									<span className="sr-only">Incorrect answer</span>
								</span>
							) : null}
						</div>
					);
				})}
			</div>
			<div className="mt-6 rounded-xl border bg-popover p-4 text-popover-foreground">
				<p className="mb-1 flex items-center gap-2 text-sm font-medium">
					<Lightbulb aria-hidden="true" className="size-4" />
					Explanation
				</p>
				<StudyText content={question.explanation_text} className="text-sm text-muted-foreground" />
			</div>
			<div className="mt-6 flex items-center justify-between">
				<Button
					type="button"
					variant="ghost"
					disabled={index === 0}
					onClick={() => moveTo(index - 1)}
				>
					<ArrowLeft /> Previous
				</Button>
				<Button
					type="button"
					variant="ghost"
					disabled={index === quiz.questions.length - 1}
					onClick={() => moveTo(index + 1)}
				>
					Next <ArrowRight />
				</Button>
			</div>
		</section>
	);
}
