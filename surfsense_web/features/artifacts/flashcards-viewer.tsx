"use client";

import { ArrowLeft, ArrowRight, Check, Eye, RotateCcw, X } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { MarkdownViewer } from "@/components/markdown-viewer";
import { Button } from "@/components/ui/button";
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
		const next = sequence[(position + offset + sequence.length) % sequence.length];
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
		} else {
			const next = sequence[nextPosition % sequence.length];
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

	const faceClass = "mx-auto flex min-h-full max-w-2xl flex-col justify-center";
	return (
		<div data-vaul-no-drag="" className="flex h-full min-h-0 flex-col bg-muted/20 p-3 sm:p-5">
			<div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
				<p>
					Card {currentIndex + 1} of {deck.cards.length}
					{reviewQueue ? ` · Reviewing missed (${position + 1}/${sequence.length})` : ""}
				</p>
				<section className="flex items-center gap-3" aria-label="Study progress">
					<span>{counts.remembered} remembered</span>
					<span>{counts.missed} missed</span>
					<span>{counts.unseen} unseen</span>
				</section>
			</div>

			<div className="min-h-0 flex-1">
				<FlashcardSurface
					revealed={revealed}
					onReveal={() => {
						setRevealed(true);
						setAnnouncement("Answer revealed");
					}}
					reducedMotion={reducedMotion}
					front={
						<div className={faceClass}>
							<p className="mb-4 text-xs font-medium uppercase tracking-wider text-muted-foreground">
								Question
							</p>
							<MarkdownViewer content={card.front_markdown} className="text-base sm:text-lg" />
							{card.hint_markdown ? (
								<div className="mt-6 border-t pt-4 text-sm text-muted-foreground">
									<span className="font-medium">Hint: </span>
									<MarkdownViewer content={card.hint_markdown} />
								</div>
							) : null}
						</div>
					}
					back={
						<div className={faceClass}>
							<p className="mb-4 text-xs font-medium uppercase tracking-wider text-muted-foreground">
								Answer
							</p>
							<MarkdownViewer content={card.back_markdown} className="text-base sm:text-lg" />
							{currentMark ? (
								<p className="mt-6 text-xs font-medium text-muted-foreground">
									Current mark: {currentMark === "good" ? "Remembered" : "Needs review"}
								</p>
							) : null}
						</div>
					}
				/>
			</div>

			<div data-vaul-no-drag="" className="mt-3 flex flex-wrap items-center justify-center gap-2">
				<Button type="button" variant="outline" size="sm" onClick={() => move(-1)}>
					<ArrowLeft className="size-4" />
					Previous
				</Button>
				{revealed ? (
					<>
						<Button
							type="button"
							variant="outline"
							size="sm"
							disabled={progressMutation.isPending}
							onClick={() => void mark("again")}
						>
							<X className="size-4" />
							Needs review
						</Button>
						<Button
							type="button"
							size="sm"
							disabled={progressMutation.isPending}
							onClick={() => void mark("good")}
						>
							<Check className="size-4" />
							Remembered
						</Button>
					</>
				) : (
					<Button
						type="button"
						size="sm"
						onClick={() => {
							setRevealed(true);
							setAnnouncement("Answer revealed");
						}}
					>
						<Eye className="size-4" />
						Reveal answer
					</Button>
				)}
				<Button type="button" variant="outline" size="sm" onClick={() => move(1)}>
					Next
					<ArrowRight className="size-4" />
				</Button>
				<Button
					type="button"
					variant="ghost"
					size="sm"
					disabled={counts.missed === 0}
					onClick={startMissedReview}
				>
					<RotateCcw className="size-4" />
					Review missed
				</Button>
			</div>
			<output className="sr-only" aria-live="polite">
				{announcement}
			</output>
		</div>
	);
}
