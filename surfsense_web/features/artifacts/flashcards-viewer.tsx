"use client";

import { ArrowLeft, ArrowRight, Check, Eye, RotateCcw, X } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { UnviewableFile } from "@/features/file-viewers/unviewable-file";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { FlashcardSurface } from "./flashcard-surface";
import {
	FLASHCARDS_MAX_VIEWER_BYTES,
	type FlashcardDeck,
	FlashcardDeckSchema,
	type FlashcardMark,
	type FlashcardProgress,
	firstUnseenCard,
	flashcardProgressCounts,
	normalizeFlashcardProgress,
} from "./flashcards-schema";
import type { ArtifactFile, ArtifactManifest } from "./model";
import { useFlashcardProgress } from "./use-flashcard-progress";

type LoadState =
	| { status: "loading" }
	| { status: "error" }
	| { status: "ready"; deck: FlashcardDeck };

function cardSequence(cardCount: number, reviewQueue: number[] | null): number[] {
	return reviewQueue ?? Array.from({ length: cardCount }, (_, index) => index);
}

export default function FlashcardsViewer({
	workspaceId,
	artifactId,
	manifest,
	primary,
}: {
	workspaceId: number;
	artifactId: number;
	manifest: ArtifactManifest;
	primary: ArtifactFile;
}) {
	const reducedMotion = useReducedMotion() ?? false;
	const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
	const [progress, setProgress] = useState<FlashcardProgress>({
		generation: manifest.generation,
		marks: {},
	});
	const [currentIndex, setCurrentIndex] = useState(0);
	const [revealed, setRevealed] = useState(false);
	const [reviewQueue, setReviewQueue] = useState<number[] | null>(null);
	const [announcement, setAnnouncement] = useState("");
	const manifestProgressRef = useRef(manifest.flashcard_progress);
	manifestProgressRef.current = manifest.flashcard_progress;
	const progressMutation = useFlashcardProgress(workspaceId, artifactId, manifest.generation);

	useEffect(() => {
		const controller = new AbortController();
		setLoadState({ status: "loading" });
		setRevealed(false);
		setReviewQueue(null);

		if (primary.size_bytes > FLASHCARDS_MAX_VIEWER_BYTES) {
			setLoadState({ status: "error" });
			return () => controller.abort();
		}

		void (async () => {
			try {
				const response = await authenticatedFetch(buildBackendUrl(primary.content_url), {
					cache: "no-store",
					signal: controller.signal,
					skipAuthRedirect: true,
				});
				if (!response.ok) throw new Error("Could not fetch flashcards");
				const bytes = new Uint8Array(await response.arrayBuffer());
				if (controller.signal.aborted) return;
				if (
					bytes.byteLength > FLASHCARDS_MAX_VIEWER_BYTES ||
					(bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf)
				) {
					throw new Error("Invalid flashcard bytes");
				}
				const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
				const parsed = FlashcardDeckSchema.safeParse(JSON.parse(text));
				if (!parsed.success) throw new Error("Invalid flashcard deck");
				const normalized = normalizeFlashcardProgress(
					manifestProgressRef.current,
					manifest.generation,
					parsed.data.cards.length
				);
				const initialIndex = firstUnseenCard(normalized, parsed.data.cards.length);
				setProgress(normalized);
				setCurrentIndex(initialIndex);
				setLoadState({ status: "ready", deck: parsed.data });
			} catch {
				if (!controller.signal.aborted) setLoadState({ status: "error" });
			}
		})();

		return () => controller.abort();
	}, [manifest.generation, primary.content_url, primary.size_bytes]);

	useEffect(() => {
		if (loadState.status !== "ready") return;
		setProgress(
			normalizeFlashcardProgress(
				manifest.flashcard_progress,
				manifest.generation,
				loadState.deck.cards.length
			)
		);
	}, [loadState, manifest.flashcard_progress, manifest.generation]);

	if (loadState.status === "loading") {
		return (
			<div aria-busy="true" className="flex h-full items-center justify-center">
				<Spinner size="lg" />
				<span className="sr-only">Loading flashcards</span>
			</div>
		);
	}
	if (loadState.status === "error") {
		return (
			<UnviewableFile message="This flashcard deck can't be displayed. Download the JSON to inspect it." />
		);
	}

	const { deck } = loadState;
	const card = deck.cards[currentIndex];
	const counts = flashcardProgressCounts(progress, deck.cards.length);
	const currentMark = progress.marks[String(currentIndex)];
	const sequence = cardSequence(deck.cards.length, reviewQueue);
	const position = sequence.indexOf(currentIndex);

	function move(offset: number) {
		const nextPosition = position + offset;
		if (nextPosition < 0 || nextPosition >= sequence.length) return;
		const next = sequence[nextPosition];
		setCurrentIndex(next);
		setRevealed(false);
		setAnnouncement(`Card ${next + 1} of ${deck.cards.length}`);
	}

	async function mark(markValue: FlashcardMark) {
		if (!revealed || progressMutation.isPending) return;
		const previousProgress = progress;
		const previousIndex = currentIndex;
		const previousQueue = reviewQueue;
		const marks = { ...progress.marks, [String(currentIndex)]: markValue };
		setProgress({ generation: manifest.generation, marks });
		setAnnouncement(markValue === "good" ? "Marked remembered" : "Marked needs review");

		const nextPosition = position + 1;
		if (reviewQueue && nextPosition >= sequence.length) {
			setReviewQueue(null);
			setRevealed(false);
			setAnnouncement("Missed-card review complete");
		} else if (nextPosition >= sequence.length) {
			setAnnouncement("Deck complete");
		} else {
			const next = sequence[nextPosition];
			setCurrentIndex(next);
			setRevealed(false);
		}

		try {
			const authoritative = await progressMutation.mutateAsync({
				cardIndex: previousIndex,
				mark: markValue,
				cardCount: deck.cards.length,
			});
			setProgress(authoritative);
		} catch {
			setProgress(previousProgress);
			setCurrentIndex(previousIndex);
			setReviewQueue(previousQueue);
			setRevealed(true);
			setAnnouncement("Progress was not saved. Try again.");
		}
	}

	function startMissedReview() {
		const missed = deck.cards.flatMap((_item, index) =>
			progress.marks[String(index)] === "again" ? [index] : []
		);
		if (missed.length === 0) return;
		setReviewQueue(missed);
		setCurrentIndex(missed[0]);
		setRevealed(false);
		setAnnouncement(`Reviewing ${missed.length} missed cards`);
	}

	const faceClass = "mx-auto flex h-full max-w-md flex-col justify-center";
	const progressValue = ((position + 1) / sequence.length) * 100;
	return (
		<div data-vaul-no-drag="" className="h-full min-h-0 overflow-y-auto bg-[#f7f7f8] p-4 sm:p-6">
			<div className="mx-auto flex min-h-full w-full max-w-[640px] flex-col items-center justify-center gap-4">
				<div className="flex w-full max-w-[560px] flex-wrap items-center justify-between gap-2 text-xs text-[#4a4a4a]">
					<p>
						{reviewQueue ? `Reviewing missed (${position + 1}/${sequence.length})` : deck.title}
					</p>
					<section className="flex items-center gap-3" aria-label="Study progress">
						<span>{counts.remembered} remembered</span>
						<span>{counts.missed} missed</span>
						<span>{counts.unseen} unseen</span>
					</section>
				</div>

				<div className="aspect-[28/17] w-full max-w-[560px] shrink-0">
					<FlashcardSurface
						revealed={revealed}
						onFlip={() => {
							setRevealed((current) => !current);
							setAnnouncement(revealed ? "Question shown" : "Answer revealed");
						}}
						reducedMotion={reducedMotion}
						front={
							<div className={faceClass}>
								<p className="mb-4 text-xs font-medium uppercase tracking-wider text-[#4a4a4a]">
									Question
								</p>
								<MarkdownViewer content={card.front_markdown} className="text-base sm:text-lg" />
								{card.hint_markdown ? (
									<div className="mt-6 border-[#d0d0d0] border-t pt-4 text-sm text-[#4a4a4a]">
										<span className="font-medium">Hint: </span>
										<MarkdownViewer content={card.hint_markdown} />
									</div>
								) : null}
							</div>
						}
						back={
							<div className={faceClass}>
								<p className="mb-4 text-xs font-medium uppercase tracking-wider text-[#4a4a4a]">
									Answer
								</p>
								<MarkdownViewer content={card.back_markdown} className="text-base sm:text-lg" />
								{currentMark ? (
									<p className="mt-6 text-xs font-medium text-[#4a4a4a]">
										Current mark: {currentMark === "good" ? "Remembered" : "Needs review"}
									</p>
								) : null}
							</div>
						}
					/>
				</div>

				<Progress
					value={progressValue}
					className="h-1.5 w-4/5 max-w-md bg-[#d0d0d0] [&>div]:bg-[#4a4a4a]"
					role="progressbar"
					aria-label="Deck progress"
					aria-valuemin={0}
					aria-valuemax={100}
					aria-valuenow={Math.round(progressValue)}
				/>

				<div data-vaul-no-drag="" className="flex h-10 items-center justify-center gap-8">
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="text-[#1c1b1e] hover:bg-[#e8e8e8] hover:text-[#1c1b1e] disabled:text-[#a9a9a9] disabled:opacity-100"
						disabled={position === 0}
						onClick={() => move(-1)}
						aria-label="Previous card"
					>
						<ArrowLeft />
					</Button>
					<p className="min-w-16 text-center text-sm text-[#4a4a4a] tabular-nums">
						{currentIndex + 1} / {deck.cards.length}
					</p>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="text-[#1c1b1e] hover:bg-[#e8e8e8] hover:text-[#1c1b1e] disabled:text-[#a9a9a9] disabled:opacity-100"
						disabled={position === sequence.length - 1}
						onClick={() => move(1)}
						aria-label="Next card"
					>
						<ArrowRight />
					</Button>
				</div>

				<div data-vaul-no-drag="" className="flex flex-wrap items-center justify-center gap-2">
					{revealed ? (
						<>
							<Button
								type="button"
								variant="outline"
								size="sm"
								className="border-[#d0d0d0] bg-white text-[#1c1b1e] hover:bg-[#f0f0f0] hover:text-[#1c1b1e]"
								disabled={progressMutation.isPending}
								onClick={() => void mark("again")}
							>
								<X data-icon="inline-start" />
								Needs review
							</Button>
							<Button
								type="button"
								size="sm"
								className="bg-[#1c1b1e] text-white hover:bg-[#4a4a4a]"
								disabled={progressMutation.isPending}
								onClick={() => void mark("good")}
							>
								<Check data-icon="inline-start" />
								Remembered
							</Button>
						</>
					) : (
						<Button
							type="button"
							size="sm"
							className="bg-[#1c1b1e] text-white hover:bg-[#4a4a4a]"
							onClick={() => {
								setRevealed(true);
								setAnnouncement("Answer revealed");
							}}
						>
							<Eye data-icon="inline-start" />
							Reveal answer
						</Button>
					)}
					<Button
						type="button"
						variant="ghost"
						size="sm"
						className="text-[#1c1b1e] hover:bg-[#e8e8e8] hover:text-[#1c1b1e]"
						disabled={counts.missed === 0}
						onClick={startMissedReview}
					>
						<RotateCcw data-icon="inline-start" />
						Review missed
					</Button>
				</div>
				<output className="sr-only" aria-live="polite">
					{announcement}
				</output>
			</div>
		</div>
	);
}
