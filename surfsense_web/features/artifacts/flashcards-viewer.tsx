"use client";

import { ArrowLeft, ArrowRight, Check, X } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { UnviewableFile } from "@/features/file-viewers/unviewable-file";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { FlashcardSurface } from "./flashcard-surface";
import { FlashcardText } from "./flashcard-text";
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
	const [announcement, setAnnouncement] = useState("");
	const manifestProgressRef = useRef(manifest.flashcard_progress);
	manifestProgressRef.current = manifest.flashcard_progress;
	const progressMutation = useFlashcardProgress(workspaceId, artifactId, manifest.generation);

	useEffect(() => {
		const controller = new AbortController();
		setLoadState({ status: "loading" });
		setRevealed(false);

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

	function move(offset: number) {
		const next = currentIndex + offset;
		if (next < 0 || next >= deck.cards.length) return;
		setCurrentIndex(next);
		setRevealed(false);
		setAnnouncement(`Card ${next + 1} of ${deck.cards.length}`);
	}

	async function mark(markValue: FlashcardMark) {
		if (progressMutation.isPending) return;
		const previousProgress = progress;
		const previousIndex = currentIndex;
		const previousRevealed = revealed;
		const marks = { ...progress.marks, [String(currentIndex)]: markValue };
		setProgress({ generation: manifest.generation, marks });
		setAnnouncement(markValue === "good" ? "Marked as got it" : "Marked needs review");

		const next = currentIndex + 1;
		if (next >= deck.cards.length) {
			setAnnouncement("Deck complete");
		} else {
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
			setRevealed(previousRevealed);
			setAnnouncement("Progress was not saved. Try again.");
		}
	}

	const faceClass = "relative mx-auto flex h-full max-w-md flex-col justify-center";
	const progressValue = ((currentIndex + 1) / deck.cards.length) * 100;
	return (
		<div data-vaul-no-drag="" className="h-full min-h-0 overflow-y-auto bg-[#f7f7f8] p-4 sm:p-6">
			<div className="mx-auto flex min-h-full w-full max-w-[640px] flex-col items-center justify-center gap-4">
				<div className="flex w-full max-w-[560px] flex-wrap items-center justify-between gap-2 text-xs text-[#4a4a4a]">
					<p>{deck.title}</p>
					<p>{counts.unseen} remaining</p>
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
								<p className="absolute top-0 left-0 text-xs text-[#a9a9a9] tabular-nums">
									{currentIndex + 1} / {deck.cards.length}
								</p>
								<p className="mb-4 text-xs font-medium uppercase tracking-wider text-[#4a4a4a]">
									Question
								</p>
								<FlashcardText
									content={card.front_text}
									className="text-sm sm:text-base lg:text-lg"
								/>
								{card.hint_text ? (
									<div className="mt-6 border-[#d0d0d0] border-t pt-4 text-sm text-[#4a4a4a]">
										<span className="font-medium">Hint: </span>
										<FlashcardText content={card.hint_text} />
									</div>
								) : null}
								<p
									aria-hidden="true"
									className="absolute inset-x-0 -bottom-5 text-center text-xs text-[#a9a9a9]"
								>
									See answer
								</p>
							</div>
						}
						back={
							<div className={faceClass}>
								<p className="absolute top-0 left-0 text-xs text-[#a9a9a9] tabular-nums">
									{currentIndex + 1} / {deck.cards.length}
								</p>
								<p className="mb-4 text-xs font-medium uppercase tracking-wider text-[#4a4a4a]">
									Answer
								</p>
								<FlashcardText
									content={card.back_text}
									className="text-sm sm:text-base lg:text-lg"
								/>
								{currentMark ? (
									<p className="mt-6 text-xs font-medium text-[#4a4a4a]">
										Current mark: {currentMark === "good" ? "Got it" : "Needs review"}
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

				<div
					data-vaul-no-drag=""
					className="flex w-full max-w-[560px] items-center justify-center gap-4 sm:gap-6"
				>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="text-[#1c1b1e] hover:bg-[#e8e8e8] hover:text-[#1c1b1e] disabled:text-[#a9a9a9] disabled:opacity-100"
						disabled={currentIndex === 0}
						onClick={() => move(-1)}
						aria-label="Previous card"
					>
						<ArrowLeft />
					</Button>
					<div className="flex min-w-0 items-center justify-center gap-2">
						<Button
							type="button"
							size="sm"
							className="h-8 bg-red-700 px-2 text-white hover:bg-red-800 sm:px-2.5"
							disabled={progressMutation.isPending}
							onClick={() => void mark("again")}
							aria-label={`Needs review, ${counts.missed} ${
								counts.missed === 1 ? "card" : "cards"
							}`}
						>
							<span className="tabular-nums">{counts.missed}</span>
							<X />
							<span className="hidden sm:inline">Needs review</span>
						</Button>
						<Button
							type="button"
							size="sm"
							className="h-8 bg-emerald-700 px-2 text-white hover:bg-emerald-800 sm:px-2.5"
							disabled={progressMutation.isPending}
							onClick={() => void mark("good")}
							aria-label={`Got it, ${counts.remembered} ${
								counts.remembered === 1 ? "card" : "cards"
							}`}
						>
							<span className="tabular-nums">{counts.remembered}</span>
							<Check />
							<span className="hidden sm:inline">Got it</span>
						</Button>
					</div>
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="text-[#1c1b1e] hover:bg-[#e8e8e8] hover:text-[#1c1b1e] disabled:text-[#a9a9a9] disabled:opacity-100"
						disabled={currentIndex === deck.cards.length - 1}
						onClick={() => move(1)}
						aria-label="Next card"
					>
						<ArrowRight />
					</Button>
				</div>
				<output className="sr-only" aria-live="polite">
					{announcement}
				</output>
			</div>
		</div>
	);
}
