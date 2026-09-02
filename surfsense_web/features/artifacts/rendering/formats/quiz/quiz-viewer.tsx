"use client";

import { Check, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Spinner } from "@/components/ui/spinner";
import {
	useRetakeQuiz,
	useSkipQuizQuestion,
	useSubmitQuizAnswer,
} from "@/features/artifacts/hooks/use-quiz-state";
import { selectPrimaryArtifactFile } from "@/features/artifacts/lib/artifact-selectors";
import type { ArtifactRendererProps } from "@/features/artifacts/model/renderer";
import { UnviewableFile } from "@/features/file-viewers/unviewable-file";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { cn } from "@/lib/utils";
import { StudyText } from "../study-text/study-text";
import { ReviewScreen } from "./review-screen";
import { QUIZ_MAX_VIEWER_BYTES, type Quiz, QuizSchema } from "./schema";
import { ScoreScreen } from "./score-screen";
import {
	emptyQuizState,
	firstUnansweredPosition,
	normalizeQuizState,
	type QuizRetakeMode,
	type QuizState,
	quizResults,
	quizRunComplete,
	retakeLocalQuiz,
	skipLocalQuestion,
	submitLocalAnswer,
} from "./state";

type LoadState = { status: "loading" } | { status: "error" } | { status: "ready"; quiz: Quiz };
type Screen = "taking" | "score" | "review";
const OPTION_LABELS = ["A", "B", "C", "D"] as const;

export default function QuizViewer({ workspaceId, manifest }: ArtifactRendererProps) {
	const primary = selectPrimaryArtifactFile(manifest);
	const headingId = useId();
	const headingRef = useRef<HTMLHeadingElement>(null);
	const manifestStateRef = useRef(manifest.quiz_state);
	manifestStateRef.current = manifest.quiz_state;
	const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
	const [quizState, setQuizState] = useState<QuizState>(() =>
		emptyQuizState(manifest.generation, 0)
	);
	const [screen, setScreen] = useState<Screen>("taking");
	const [currentPosition, setCurrentPosition] = useState(0);
	const [reviewIndex, setReviewIndex] = useState(0);
	const [selectedOption, setSelectedOption] = useState<number | null>(null);
	const [message, setMessage] = useState("");
	const submitAnswer = useSubmitQuizAnswer(workspaceId, manifest.artifact_id, manifest.generation);
	const skipQuestion = useSkipQuizQuestion(workspaceId, manifest.artifact_id, manifest.generation);
	const retake = useRetakeQuiz(workspaceId, manifest.artifact_id, manifest.generation);
	const persisted = manifest.quiz_state !== undefined;
	const primaryContentUrl = primary?.content_url;
	const primarySizeBytes = primary?.size_bytes;

	useEffect(() => {
		const controller = new AbortController();
		setLoadState({ status: "loading" });
		setScreen("taking");
		setSelectedOption(null);
		if (
			!primaryContentUrl ||
			primarySizeBytes === undefined ||
			primarySizeBytes > QUIZ_MAX_VIEWER_BYTES
		) {
			setLoadState({ status: "error" });
			return () => controller.abort();
		}

		void (async () => {
			try {
				const response = await authenticatedFetch(buildBackendUrl(primaryContentUrl), {
					cache: "no-store",
					signal: controller.signal,
					skipAuthRedirect: true,
				});
				if (!response.ok) throw new Error("Could not fetch quiz");
				const bytes = new Uint8Array(await response.arrayBuffer());
				if (
					controller.signal.aborted ||
					bytes.byteLength > QUIZ_MAX_VIEWER_BYTES ||
					(bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf)
				) {
					throw new Error("Invalid quiz bytes");
				}
				const parsed = QuizSchema.safeParse(
					JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes))
				);
				if (!parsed.success) throw new Error("Invalid quiz");
				const state = normalizeQuizState(
					manifestStateRef.current,
					manifest.generation,
					parsed.data.questions.length
				);
				setQuizState(state);
				setCurrentPosition(firstUnansweredPosition(state));
				setScreen(quizRunComplete(state) ? "score" : "taking");
				setLoadState({ status: "ready", quiz: parsed.data });
			} catch {
				if (!controller.signal.aborted) setLoadState({ status: "error" });
			}
		})();
		return () => controller.abort();
	}, [manifest.generation, primaryContentUrl, primarySizeBytes]);

	useEffect(() => {
		if (!persisted || loadState.status !== "ready") return;
		setQuizState(
			normalizeQuizState(manifest.quiz_state, manifest.generation, loadState.quiz.questions.length)
		);
	}, [loadState, manifest.generation, manifest.quiz_state, persisted]);

	if (loadState.status === "loading") {
		return (
			<div aria-busy="true" className="flex h-full items-center justify-center">
				<Spinner size="lg" />
				<span className="sr-only">Loading quiz</span>
			</div>
		);
	}
	if (loadState.status === "error") {
		return <UnviewableFile message="This quiz can't be displayed." />;
	}

	const { quiz } = loadState;
	const results = quizResults(quiz, quizState);
	const questionIndex = quizState.active_question_indices[currentPosition] ?? 0;
	const question = quiz.questions[questionIndex];
	const submittedOption = quizState.answers[String(questionIndex)];
	const answerRevealed = submittedOption !== undefined;
	const isLastQuestion = currentPosition === quizState.active_question_indices.length - 1;
	const savingQuestion = submitAnswer.isPending || skipQuestion.isPending;

	async function selectAnswer(optionIndex: number) {
		if (answerRevealed || savingQuestion) return;
		setSelectedOption(optionIndex);
		setMessage("");
		try {
			const state = persisted
				? await submitAnswer.mutateAsync({
						question_index: questionIndex,
						selected_option_index: optionIndex,
					})
				: submitLocalAnswer(quizState, questionIndex, optionIndex);
			setQuizState(state);
		} catch (error) {
			setSelectedOption(null);
			setMessage(error instanceof Error ? error.message : "Answer could not be saved");
		}
	}

	function moveForward() {
		setSelectedOption(null);
		if (isLastQuestion) {
			setScreen("score");
		} else {
			setCurrentPosition((position) => position + 1);
			requestAnimationFrame(() => headingRef.current?.focus());
		}
	}

	async function skip() {
		if (answerRevealed || savingQuestion) return;
		setMessage("");
		try {
			const state = persisted
				? await skipQuestion.mutateAsync({ question_index: questionIndex })
				: skipLocalQuestion(quizState, questionIndex);
			setQuizState(state);
			moveForward();
		} catch (error) {
			setMessage(error instanceof Error ? error.message : "Question could not be skipped");
		}
	}

	async function startRetake(mode: QuizRetakeMode) {
		if (retake.isPending) return;
		setMessage("");
		try {
			const state = persisted
				? await retake.mutateAsync({ mode })
				: retakeLocalQuiz(quiz, quizState, mode);
			setQuizState(state);
			setCurrentPosition(0);
			setSelectedOption(null);
			setScreen("taking");
			requestAnimationFrame(() => headingRef.current?.focus());
		} catch (error) {
			setMessage(error instanceof Error ? error.message : "Quiz could not be restarted");
		}
	}

	return (
		<div
			data-vaul-no-drag=""
			className="h-full min-h-0 overflow-y-auto bg-sidebar p-4 text-sidebar-foreground sm:p-6"
		>
			<div className="mx-auto flex min-h-full w-full max-w-2xl flex-col justify-center">
				{screen === "taking" ? (
					<section aria-labelledby={headingId}>
						<div className="mb-6 flex items-center justify-between gap-4 text-sm text-muted-foreground">
							<p className="truncate">{quiz.title}</p>
							<p className="shrink-0 tabular-nums">
								{currentPosition + 1} / {quizState.active_question_indices.length}
							</p>
						</div>
						<Progress
							value={
								((currentPosition + (answerRevealed ? 1 : 0)) /
									quizState.active_question_indices.length) *
								100
							}
							className="mb-8 h-1.5"
							role="progressbar"
							aria-label="Quiz progress"
						/>
						<h2
							id={headingId}
							ref={headingRef}
							tabIndex={-1}
							className="mb-6 text-balance text-xl font-semibold outline-none sm:text-2xl"
						>
							<StudyText content={question.question_text} />
						</h2>
						<RadioGroup
							value={selectedOption === null ? "" : String(selectedOption)}
							onValueChange={(value) => void selectAnswer(Number(value))}
							disabled={answerRevealed || savingQuestion}
							aria-label={`Question ${questionIndex + 1} options`}
							className="gap-3"
						>
							{question.options.map((option, index) => {
								const optionId = `${headingId}-option-${index}`;
								const isCorrect = index === question.correct_option_index;
								const isSubmitted = index === submittedOption;
								return (
									<label
										key={optionId}
										htmlFor={optionId}
										className={cn(
											"flex min-h-14 items-center gap-3 rounded-xl border p-4 transition-colors",
											answerRevealed
												? "cursor-default"
												: "cursor-pointer hover:border-foreground/25 hover:bg-muted/50",
											answerRevealed && isCorrect && "border-green-500",
											answerRevealed && isSubmitted && !isCorrect && "border-red-500",
											!answerRevealed && selectedOption === index && "border-primary"
										)}
									>
										<RadioGroupItem id={optionId} value={String(index)} />
										<span className="flex min-w-0 flex-1 gap-3">
											<span className="font-medium text-muted-foreground">
												{OPTION_LABELS[index]}.
											</span>
											<StudyText content={option} />
										</span>
										{answerRevealed && isCorrect ? (
											<span className="text-green-600 dark:text-green-400">
												<Check aria-hidden="true" className="size-5" />
												<span className="sr-only">Correct answer</span>
											</span>
										) : answerRevealed && isSubmitted ? (
											<span className="text-red-600 dark:text-red-400">
												<X aria-hidden="true" className="size-5" />
												<span className="sr-only">Incorrect answer</span>
											</span>
										) : null}
									</label>
								);
							})}
						</RadioGroup>
						<div className="mt-6 flex justify-end">
							<Button
								type="button"
								disabled={savingQuestion}
								onClick={answerRevealed ? moveForward : () => void skip()}
								className="relative w-28 border-0 bg-white text-black hover:bg-white/90 hover:text-black dark:bg-white dark:text-black dark:hover:bg-white/90 dark:hover:text-black"
							>
								<span className={savingQuestion ? "opacity-0" : ""}>
									{answerRevealed ? (isLastQuestion ? "View score" : "Next") : "Skip"}
								</span>
								{savingQuestion ? <Spinner size="sm" className="absolute" /> : null}
							</Button>
						</div>
					</section>
				) : screen === "score" ? (
					<ScoreScreen
						quiz={quiz}
						correct={results.correct}
						missed={results.missed}
						skipped={results.skipped}
						percentage={results.percentage}
						pending={retake.isPending}
						onReview={(index) => {
							setReviewIndex(index);
							setScreen("review");
						}}
						onRetake={(mode) => void startRetake(mode)}
					/>
				) : (
					<ReviewScreen
						quiz={quiz}
						state={quizState}
						index={reviewIndex}
						onIndexChange={setReviewIndex}
						onExit={() => setScreen("score")}
					/>
				)}
				{message ? (
					<p role="alert" className="mt-4 text-sm text-destructive">
						{message}
					</p>
				) : null}
			</div>
		</div>
	);
}
