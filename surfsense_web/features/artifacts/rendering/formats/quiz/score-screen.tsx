"use client";

import { ChevronDown, ChevronRight, Dot, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { StudyText } from "../study-text/study-text";
import type { Quiz } from "./schema";
import type { QuizRetakeMode } from "./state";

type ResultCategory = "correct" | "missed" | "skipped";

function QuestionSection({
	title,
	indices,
	quiz,
	onReview,
}: {
	title: string;
	indices: number[];
	quiz: Quiz;
	onReview: (index: number) => void;
}) {
	return (
		<section>
			<h3 className="font-medium">
				{title} ({indices.length})
			</h3>
			{indices.length > 0 ? (
				<ol className="mt-2 space-y-1">
					{indices.map((index) => (
						<li key={index}>
							<button
								type="button"
								onClick={() => onReview(index)}
								aria-label={`Review question ${index + 1}`}
								className="flex w-full items-start gap-3 rounded-lg p-2 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
							>
								<span className="font-medium text-foreground">{index + 1}.</span>
								<span className="min-w-0 flex-1">
									<StudyText content={quiz.questions[index].question_text} />
								</span>
								<ChevronRight aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
							</button>
						</li>
					))}
				</ol>
			) : (
				<p className="mt-2 text-sm text-muted-foreground">None</p>
			)}
		</section>
	);
}

export function ScoreScreen({
	quiz,
	correct,
	missed,
	skipped,
	percentage,
	pending,
	onReview,
	onRetake,
}: {
	quiz: Quiz;
	correct: number;
	missed: number[];
	skipped: number[];
	percentage: number;
	pending: boolean;
	onReview: (index: number) => void;
	onRetake: (mode: QuizRetakeMode) => void;
}) {
	const headingRef = useRef<HTMLHeadingElement>(null);
	const [category, setCategory] = useState<ResultCategory>("missed");
	useEffect(() => headingRef.current?.focus(), []);
	const unresolved = new Set([...missed, ...skipped]);
	const correctIndices = quiz.questions
		.map((_, index) => index)
		.filter((index) => !unresolved.has(index));
	const selectCategory = (value: string) => {
		if (value === "correct" || value === "missed" || value === "skipped") setCategory(value);
	};
	const questionCount = quiz.questions.length;

	return (
		<section className="rounded-2xl border p-5 sm:p-7">
			<div className="flex flex-wrap items-start justify-between gap-4">
				<div>
					<p className="text-sm text-muted-foreground">Your score</p>
					<h2
						ref={headingRef}
						tabIndex={-1}
						className="mt-1 text-4xl font-semibold tracking-tight outline-none"
					>
						{correct}/{quiz.questions.length}{" "}
						<span className="text-muted-foreground">({percentage}%)</span>
					</h2>
				</div>
				<Button
					type="button"
					variant="outline"
					onClick={() => onReview(0)}
					className="border-0 bg-white text-black hover:bg-white/90 hover:text-black dark:bg-white dark:text-black dark:hover:bg-white/90 dark:hover:text-black"
				>
					Review
				</Button>
			</div>
			<fieldset className="mt-7 flex h-5 overflow-hidden rounded-full bg-muted">
				<legend className="sr-only">Score breakdown</legend>
				<button
					type="button"
					aria-label={`Show ${correct} correct questions`}
					onClick={() => setCategory("correct")}
					className={cn(
						"rounded-l-full border-2 border-transparent bg-brand transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
						missed.length === 0 && skipped.length === 0 && "rounded-r-full",
						category === "correct" && "border-white"
					)}
					style={{ width: `${(correct / questionCount) * 100}%` }}
				/>
				<button
					type="button"
					aria-label={`Show ${missed.length} missed questions`}
					onClick={() => setCategory("missed")}
					className={cn(
						"border-2 border-transparent bg-brand/25 transition-colors hover:bg-brand/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
						correct === 0 && "rounded-l-full",
						skipped.length === 0 && "rounded-r-full",
						category === "missed" && "border-white"
					)}
					style={{ width: `${(missed.length / questionCount) * 100}%` }}
				/>
				<button
					type="button"
					aria-label={`Show ${skipped.length} skipped questions`}
					onClick={() => setCategory("skipped")}
					className={cn(
						"min-w-0 flex-1 rounded-r-full border-2 border-transparent bg-muted transition-colors hover:bg-muted/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
						correct === 0 && missed.length === 0 && "rounded-l-full",
						category === "skipped" && "border-white"
					)}
				/>
			</fieldset>
			<Tabs value={category} onValueChange={selectCategory} className="mt-4">
				<TabsList className="h-auto justify-start gap-0.5 bg-transparent p-0 sm:gap-2">
					<TabsTrigger
						value="correct"
						className="gap-0.5 rounded-full border border-transparent px-1.5 py-1 text-xs data-[state=active]:border-border sm:gap-1.5 sm:px-3 sm:py-1.5 sm:text-sm"
					>
						<Dot aria-hidden="true" className="size-3.5 text-brand sm:size-5" strokeWidth={8} />
						{correct} correct
					</TabsTrigger>
					<TabsTrigger
						value="missed"
						className="gap-0.5 rounded-full border border-transparent px-1.5 py-1 text-xs data-[state=active]:border-border sm:gap-1.5 sm:px-3 sm:py-1.5 sm:text-sm"
					>
						<Dot aria-hidden="true" className="size-3.5 text-brand/40 sm:size-5" strokeWidth={8} />
						{missed.length} missed
					</TabsTrigger>
					<TabsTrigger
						value="skipped"
						className="gap-0.5 rounded-full border border-transparent px-1.5 py-1 text-xs data-[state=active]:border-border sm:gap-1.5 sm:px-3 sm:py-1.5 sm:text-sm"
					>
						<Dot
							aria-hidden="true"
							className="size-3.5 text-muted-foreground sm:size-5"
							strokeWidth={8}
						/>
						{skipped.length} skipped
					</TabsTrigger>
				</TabsList>
				<div className="mt-7 h-72 overflow-y-auto border-t pt-5 pr-2">
					<TabsContent value="correct" className="mt-0">
						<QuestionSection
							title="Correct"
							indices={correctIndices}
							quiz={quiz}
							onReview={onReview}
						/>
					</TabsContent>
					<TabsContent value="missed" className="mt-0">
						<QuestionSection title="Missed" indices={missed} quiz={quiz} onReview={onReview} />
					</TabsContent>
					<TabsContent value="skipped" className="mt-0">
						<QuestionSection title="Skipped" indices={skipped} quiz={quiz} onReview={onReview} />
					</TabsContent>
				</div>
			</Tabs>
			<div className="mt-7 flex justify-end border-t pt-5">
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<Button
							type="button"
							variant="outline"
							disabled={pending}
							className="relative border-0 bg-white text-black hover:bg-white/90 hover:text-black dark:bg-white dark:text-black dark:hover:bg-white/90 dark:hover:text-black"
						>
							<span
								className={
									pending
										? "inline-flex items-center gap-2 opacity-0"
										: "inline-flex items-center gap-2"
								}
							>
								<RotateCcw /> Retake quiz <ChevronDown />
							</span>
							{pending ? <Spinner size="sm" className="absolute" /> : null}
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end" className="z-90">
						<DropdownMenuItem
							disabled={missed.length + skipped.length === 0}
							onSelect={() => onRetake("missed")}
						>
							Retake missed questions
						</DropdownMenuItem>
						<DropdownMenuItem onSelect={() => onRetake("all")}>
							Retake all questions
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
		</section>
	);
}
