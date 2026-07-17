"use client";

import { ArrowUp, ChevronRightIcon, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { TextShimmerLoader } from "@/components/prompt-kit/loader";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type HeroChatDemoStep = {
	/** Timeline row title, phrased like the real tool display names ("Read webpage"). */
	title: string;
	/** Optional sub-bullets shown under the title while/after the step runs. */
	items?: string[];
};

export type HeroChatDemoScript = {
	/** The query the typewriter types and "sends". */
	prompt: string;
	/** Agent timeline steps, run sequentially like the real chat timeline. */
	steps: HeroChatDemoStep[];
	/** Bullet list in the final streamed answer. */
	rows: { primary: string; secondary: string }[];
	/** Closing line of the answer. */
	summary: string;
};

type Stage = "typing" | "steps" | "answer" | "done";

const PLACEHOLDER =
	"Research the live web, scrape platforms, automate briefs. Use / for prompts, @ for docs";

/** Blinking caret for the typewriter (overlay only, never inside the real input). */
function Caret() {
	return (
		<span className="ml-px inline-block h-4 w-0.5 animate-pulse bg-foreground align-text-bottom" />
	);
}

/** Status dot cloned from the real timeline: pulsing while running, muted when settled. */
function StatusDot({ running }: { running: boolean }) {
	if (running) {
		return (
			<span className="relative flex size-2">
				<span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60" />
				<span className="relative inline-flex size-2 rounded-full bg-primary" />
			</span>
		);
	}
	return <span className="size-2 rounded-full bg-muted-foreground/30" />;
}

/** Clone of the chat's collapsible agent timeline (dots, connector lines, shimmer header). */
function DemoTimeline({
	steps,
	startedCount,
	runningIndex,
	settled,
}: {
	steps: HeroChatDemoStep[];
	startedCount: number;
	runningIndex: number;
	settled: boolean;
}) {
	const [isOpen, setIsOpen] = useState(true);

	// Mirror the real timeline: open while processing, auto-collapse once settled.
	useEffect(() => {
		setIsOpen(!settled);
	}, [settled]);

	const visible = steps.slice(0, startedCount);
	const headerText = settled ? "Reviewed" : (steps[runningIndex]?.title ?? "Processing");

	return (
		<div className="w-full">
			<Button
				variant="ghost"
				type="button"
				onClick={() => setIsOpen((prev) => !prev)}
				className="h-auto w-full justify-start gap-1.5 p-0 text-left text-sm font-normal text-muted-foreground transition-colors hover:bg-transparent hover:text-accent-foreground"
			>
				{settled ? <span>{headerText}</span> : <TextShimmerLoader text={headerText} size="sm" />}
				<ChevronRightIcon
					className={cn("size-4 transition-transform duration-200", isOpen && "rotate-90")}
				/>
			</Button>

			<div
				className={cn(
					"grid transition-[grid-template-rows] duration-300 ease-out",
					isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
				)}
			>
				<div className="overflow-hidden">
					<div className="mt-3 pl-1">
						{visible.map((step, i) => {
							const running = !settled && i === runningIndex;
							const isLast = i === visible.length - 1;
							return (
								<div key={step.title} className="relative flex gap-3">
									<div className="relative flex w-2 flex-col items-center self-stretch">
										{!isLast && (
											<div className="absolute left-1/2 top-[15px] -bottom-[15px] w-px -translate-x-1/2 bg-muted-foreground/30" />
										)}
										<div className="relative z-10 mt-[7px] flex shrink-0 items-center justify-center">
											<StatusDot running={running} />
										</div>
									</div>
									<div className="min-w-0 flex-1 pb-4">
										<div
											className={cn(
												"text-sm leading-5",
												running ? "font-medium text-foreground" : "text-muted-foreground"
											)}
										>
											{step.title}
										</div>
										{step.items && step.items.length > 0 && (
											<div className="mt-1 space-y-0.5">
												{step.items.map((item) => (
													<div
														key={item}
														className="flex items-start gap-1.5 text-xs text-muted-foreground"
													>
														<span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground/40" />
														<span className="min-w-0">{item}</span>
													</div>
												))}
											</div>
										)}
									</div>
								</div>
							);
						})}
					</div>
				</div>
			</div>
		</div>
	);
}

/**
 * Scripted clone of the new-chat UI: the demo types a use-case prompt into the
 * composer, sends it, walks the agent timeline (like the real chat), then
 * streams the answer. Focusing the input pauses the demo (it resumes on empty
 * blur); sending anything routes to /login.
 */
export function HeroChatDemo({
	demo,
	reduceMotion,
}: {
	demo: HeroChatDemoScript;
	reduceMotion: boolean;
}) {
	const router = useRouter();
	const viewportRef = useRef<HTMLDivElement>(null);
	const [interrupted, setInterrupted] = useState(false);
	const [userText, setUserText] = useState("");
	const [stage, setStage] = useState<Stage>("typing");
	const [typed, setTyped] = useState("");
	const [sent, setSent] = useState(false);
	const [startedSteps, setStartedSteps] = useState(0);
	const [revealedRows, setRevealedRows] = useState(0);

	const animating = !reduceMotion && !interrupted;

	useEffect(() => {
		if (!animating) return;
		let cancelled = false;
		let timer: ReturnType<typeof setTimeout>;
		const wait = (ms: number) =>
			new Promise<void>((resolve) => {
				timer = setTimeout(resolve, ms);
			});

		(async () => {
			while (!cancelled) {
				setStage("typing");
				setTyped("");
				setSent(false);
				setStartedSteps(0);
				setRevealedRows(0);
				await wait(700);
				for (let i = 1; i <= demo.prompt.length; i++) {
					if (cancelled) return;
					setTyped(demo.prompt.slice(0, i));
					await wait(20);
				}
				await wait(550);
				if (cancelled) return;
				setSent(true);
				setTyped("");
				setStage("steps");
				await wait(500);
				for (let i = 1; i <= demo.steps.length; i++) {
					if (cancelled) return;
					setStartedSteps(i);
					await wait(1400);
				}
				if (cancelled) return;
				setStage("answer");
				await wait(500); // timeline collapse
				for (let i = 1; i <= demo.rows.length; i++) {
					if (cancelled) return;
					setRevealedRows(i);
					await wait(500);
				}
				await wait(350);
				setStage("done");
				await wait(5600);
			}
		})();

		return () => {
			cancelled = true;
			clearTimeout(timer);
		};
	}, [animating, demo]);

	// Keep the newest streamed content visible in the small viewport.
	// biome-ignore lint/correctness/useExhaustiveDependencies: demo progress states are scroll triggers, not effect inputs
	useEffect(() => {
		const el = viewportRef.current;
		if (el) el.scrollTop = el.scrollHeight;
	}, [stage, startedSteps, revealedRows, sent]);

	// Reduced motion: show the finished conversation instead of looping.
	const showSent = reduceMotion ? true : !interrupted && sent;
	const shownStage: Stage = reduceMotion ? "done" : stage;
	const shownSteps = reduceMotion ? demo.steps.length : startedSteps;
	const shownRows = reduceMotion ? demo.rows.length : revealedRows;
	const stepsSettled = shownStage === "answer" || shownStage === "done";

	const handleSend = () => {
		router.push("/login");
	};

	const composer = (
		<div className="rounded-3xl border border-input/20 bg-muted pt-2 shadow-sm shadow-black/5 transition-[border-color] focus-within:border-input/60 hover:border-input/60">
			<div className="relative px-4 pt-1 pb-1">
				<textarea
					rows={2}
					value={userText}
					onChange={(e) => setUserText(e.target.value)}
					onFocus={() => setInterrupted(true)}
					onBlur={() => {
						if (!userText.trim()) setInterrupted(false);
					}}
					onKeyDown={(e) => {
						if (e.key === "Enter" && !e.shiftKey) {
							e.preventDefault();
							handleSend();
						}
					}}
					placeholder={interrupted ? PLACEHOLDER : undefined}
					aria-label="Try SurfSense: describe a task for your agent"
					className="w-full resize-none bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
				/>
				{!interrupted && (
					<div
						aria-hidden
						className="pointer-events-none absolute inset-0 overflow-hidden px-4 pt-1 pb-1 text-sm"
					>
						{typed ? (
							<span className="text-foreground">
								{typed}
								<Caret />
							</span>
						) : (
							<span className="text-muted-foreground">{PLACEHOLDER}</span>
						)}
					</div>
				)}
			</div>
			{/* Action bar: attach on the left, round send on the right */}
			<div className="mx-3 mb-3 flex items-center justify-between">
				<span
					aria-hidden
					className="flex size-8 items-center justify-center rounded-full text-muted-foreground"
				>
					<Plus className="size-4" />
				</span>
				<Button
					type="button"
					size="icon"
					onClick={handleSend}
					aria-label="Send message"
					className="size-9 shrink-0 rounded-full"
				>
					<ArrowUp className="size-5" />
				</Button>
			</div>
		</div>
	);

	return (
		<div className="flex h-88 flex-col overflow-hidden rounded-lg border bg-background sm:h-96 sm:rounded-xl">
			{showSent ? (
				<>
					{/* Messages viewport */}
					<div
						ref={viewportRef}
						className="flex-1 overflow-y-auto px-3 py-3 sm:px-4"
						aria-hidden={!interrupted}
					>
						<div className="space-y-3">
							{/* User message (real bubble style) */}
							<div className="flex justify-end pl-8">
								<div className="wrap-break-word rounded-xl bg-muted px-4 py-2.5 text-sm text-foreground">
									{demo.prompt}
								</div>
							</div>

							{/* Agent timeline */}
							{shownSteps > 0 && (
								<DemoTimeline
									steps={demo.steps}
									startedCount={shownSteps}
									runningIndex={shownSteps - 1}
									settled={stepsSettled}
								/>
							)}

							{/* Streamed answer */}
							{stepsSettled && shownRows > 0 && (
								<div className="space-y-2 pr-6 text-sm leading-relaxed text-foreground">
									<ul className="space-y-1.5">
										{demo.rows.slice(0, shownRows).map((row) => (
											<li
												key={row.primary}
												className="fade-in slide-in-from-bottom-1 flex animate-in items-start gap-2 duration-200"
											>
												<span className="mt-2 size-1 shrink-0 rounded-full bg-foreground/60" />
												<span className="min-w-0">
													<span className="font-medium">{row.primary}</span>
													<span className="text-muted-foreground"> — {row.secondary}</span>
												</span>
											</li>
										))}
									</ul>
									{shownStage === "done" && (
										<p className="fade-in animate-in text-muted-foreground duration-300">
											{demo.summary}
										</p>
									)}
								</div>
							)}
						</div>
					</div>
					{/* Composer docked at the bottom while a thread is active */}
					<div className="p-2 sm:p-3">{composer}</div>
				</>
			) : (
				/* Empty thread: composer centered, like the real new-chat welcome */
				<div className="flex flex-1 items-center p-3 sm:p-4">
					<div className="w-full">{composer}</div>
				</div>
			)}
		</div>
	);
}
