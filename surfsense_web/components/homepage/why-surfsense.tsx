"use client";

import { useRef, useState } from "react";
import { motion, useInView } from "motion/react";
import { IconPointerFilled } from "@tabler/icons-react";
import { Check, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

const cards = [
	{
		title: "Unlimited & Self-Hosted",
		description:
			"No caps on sources, notebooks, or file sizes. Deploy on your own infra and your data never leaves your control.",
		skeleton: <UnlimitedSkeleton />,
	},
	{
		title: "100+ LLMs, Zero Lock-in",
		description:
			"Swap between 100+ LLMs via OpenAI spec and LiteLLM, or run fully private with vLLM, Ollama, and more.",
		skeleton: <LLMFlexibilitySkeleton />,
	},
	{
		title: "Real-Time Multiplayer",
		description:
			"RBAC with Owner, Admin, Editor, and Viewer roles plus real-time chat and comment threads. Built for teams.",
		skeleton: <MultiplayerSkeleton />,
	},
];

export function WhySurfSense() {
	return (
		<section className="px-4 py-10 md:px-8 md:py-24 lg:px-16 lg:py-32">
			<div className="mx-auto mb-10 max-w-3xl text-center md:mb-16">
				<p className="mb-3 text-sm font-semibold uppercase tracking-widest text-brand">
					Why SurfSense
				</p>
				<h2 className="text-balance text-3xl font-bold tracking-tight text-foreground sm:text-4xl lg:text-5xl">
					Everything NotebookLM should have been
				</h2>
				<p className="mx-auto mt-4 max-w-2xl text-base text-muted-foreground">
					Open source. No data limits. No vendor lock-in. Built for teams that
					care about privacy and flexibility.
				</p>
			</div>

			<div className="mx-auto grid w-full max-w-6xl grid-cols-1 divide-x-0 divide-y divide-border overflow-hidden rounded-2xl shadow-sm ring-1 ring-border md:grid-cols-3 md:divide-x md:divide-y-0">
				{cards.map((card) => (
					<FeatureCard key={card.title} {...card} />
				))}
			</div>

			<ComparisonStrip />
		</section>
	);
}

function UnlimitedSkeleton({ className }: { className?: string }) {
	const ref = useRef(null);
	const isInView = useInView(ref, { once: true, margin: "-50px" });

	const items = [
		{ label: "Sources", notebookLm: "50-600", surfSense: "Unlimited", icon: "📄" },
		{ label: "Notebooks", notebookLm: "100-500", surfSense: "Unlimited", icon: "📓" },
		{ label: "File size", notebookLm: "200 MB", surfSense: "No limit", icon: "📦" },
		{ label: "Self-host", notebookLm: "No", surfSense: "Yes", icon: "🏠" },
	];

	return (
		<div
			ref={ref}
			className={cn("flex h-full flex-col justify-center gap-2.5", className)}
		>
			{items.map((item, index) => (
				<motion.div
					key={item.label}
					initial={{ opacity: 0, x: -16 }}
					animate={isInView ? { opacity: 1, x: 0 } : {}}
					transition={{ duration: 0.35, delay: index * 0.15 }}
					className="flex items-center gap-2 rounded-lg bg-background px-3 py-2 shadow-sm ring-1 ring-border"
				>
					<span className="text-sm">{item.icon}</span>
					<span className="min-w-[60px] text-xs font-medium text-foreground">
						{item.label}
					</span>
					<div className="ml-auto flex items-center gap-2">
						<span className="text-[10px] text-muted-foreground line-through">
							{item.notebookLm}
						</span>
						<motion.div
							initial={{ scale: 0.8 }}
							animate={isInView ? { scale: 1 } : {}}
							transition={{
								duration: 0.3,
								delay: index * 0.15 + 0.2,
								type: "spring",
								stiffness: 300,
							}}
						>
							<Badge variant="secondary" className="text-[10px] px-1.5 py-0">
								{item.surfSense}
							</Badge>
						</motion.div>
					</div>
				</motion.div>
			))}
		</div>
	);
}

function LLMFlexibilitySkeleton({ className }: { className?: string }) {
	const ref = useRef(null);
	const isInView = useInView(ref, { once: true, margin: "-50px" });
	const [selected, setSelected] = useState(0);

	const models = [
		{ name: "GPT-4o", provider: "OpenAI", color: "bg-green-500" },
		{ name: "Claude 4", provider: "Anthropic", color: "bg-orange-500" },
		{ name: "Gemini 2.5", provider: "Google", color: "bg-blue-500" },
		{ name: "Llama 4", provider: "Local", color: "bg-purple-500" },
		{ name: "DeepSeek R1", provider: "DeepSeek", color: "bg-cyan-500" },
	];

	return (
		<div
			ref={ref}
			className={cn(
				"flex h-full flex-col items-center justify-center gap-3",
				className,
			)}
		>
			<motion.div
				initial={{ opacity: 0, y: 8 }}
				animate={isInView ? { opacity: 1, y: 0 } : {}}
				transition={{ duration: 0.3 }}
				className="flex w-full max-w-[180px] flex-col gap-1.5"
			>
				{models.map((model, index) => (
					<motion.button
						key={model.name}
						type="button"
						onClick={() => setSelected(index)}
						initial={{ opacity: 0, x: 12 }}
						animate={isInView ? { opacity: 1, x: 0 } : {}}
						transition={{ duration: 0.3, delay: 0.1 + index * 0.1 }}
						className={cn(
							"flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-left transition-all",
							selected === index
								? "bg-background shadow-sm ring-1 ring-border"
								: "hover:bg-accent",
						)}
					>
						<div className={cn("size-2 shrink-0 rounded-full", model.color)} />
						<div className="min-w-0">
							<p className="truncate text-xs font-medium text-foreground">
								{model.name}
							</p>
							<p className="text-[10px] text-muted-foreground">
								{model.provider}
							</p>
						</div>
						{selected === index && (
							<motion.div
								layoutId="model-check"
								className="ml-auto"
								transition={{ type: "spring", stiffness: 400, damping: 25 }}
							>
								<Check className="size-3 text-brand" />
							</motion.div>
						)}
					</motion.button>
				))}
			</motion.div>
		</div>
	);
}

function MultiplayerSkeleton({ className }: { className?: string }) {
	const ref = useRef(null);
	const isInView = useInView(ref, { once: true, margin: "-50px" });

	const collaborators = [
		{
			id: 1,
			name: "Alice",
			role: "Editor",
			color: "#3b82f6",
			path: [
				{ x: 15, y: 10 },
				{ x: 80, y: 40 },
				{ x: 40, y: 80 },
				{ x: 15, y: 10 },
			],
		},
		{
			id: 2,
			name: "Bob",
			role: "Viewer",
			color: "#10b981",
			path: [
				{ x: 115, y: 70 },
				{ x: 55, y: 20 },
				{ x: 95, y: 50 },
				{ x: 115, y: 70 },
			],
		},
	];

	const codeLines = [
		{ indent: 0, width: "60%", color: "bg-chart-4/60" },
		{ indent: 1, width: "75%", color: "bg-muted-foreground/20" },
		{ indent: 1, width: "50%", color: "bg-chart-1/60" },
		{ indent: 2, width: "80%", color: "bg-muted-foreground/20" },
		{ indent: 2, width: "45%", color: "bg-chart-2/60" },
		{ indent: 1, width: "30%", color: "bg-muted-foreground/20" },
		{ indent: 0, width: "20%", color: "bg-chart-4/60" },
	];

	return (
		<div
			ref={ref}
			className={cn(
				"relative flex h-full items-center justify-center overflow-visible",
				className,
			)}
		>
			<motion.div
				className="relative w-full max-w-[160px] rounded-lg bg-background p-3 shadow-sm ring-1 ring-border"
				initial={{ opacity: 0, y: 10 }}
				animate={isInView ? { opacity: 1, y: 0 } : {}}
				transition={{ duration: 0.4 }}
			>
				<div className="mb-2 flex items-center gap-1.5">
					<div className="flex gap-1">
						<div className="size-1.5 rounded-full bg-red-400" />
						<div className="size-1.5 rounded-full bg-yellow-400" />
						<div className="size-1.5 rounded-full bg-green-400" />
					</div>
					<div className="ml-2 h-1.5 w-12 rounded-full bg-muted" />
				</div>

				{codeLines.map((line, index) => (
					<div
						key={index}
						className="my-1.5 flex items-center"
						style={{ paddingLeft: line.indent * 8 }}
					>
						<div
							className={cn("h-1.5 rounded-full", line.color)}
							style={{ width: line.width }}
						/>
					</div>
				))}
			</motion.div>

			{collaborators.map((collaborator, index) => (
				<motion.div
					key={collaborator.id}
					className="absolute"
					initial={{ opacity: 0 }}
					animate={
						isInView
							? {
									opacity: 1,
									x: collaborator.path.map((p) => p.x),
									y: collaborator.path.map((p) => p.y),
								}
							: {}
					}
					transition={{
						opacity: { duration: 0.3, delay: 0.5 + index * 0.2 },
						x: {
							duration: 6,
							delay: 0.5 + index * 0.3,
							repeat: Infinity,
							ease: "easeInOut",
						},
						y: {
							duration: 6,
							delay: 0.5 + index * 0.3,
							repeat: Infinity,
							ease: "easeInOut",
						},
					}}
				>
					<IconPointerFilled
						className="size-5 drop-shadow-sm"
						style={{ color: collaborator.color }}
					/>
					<div
						className="absolute top-5 left-3 z-50 flex w-max items-center gap-1.5 rounded-full py-1 pr-2.5 pl-1 shadow-sm"
						style={{ backgroundColor: collaborator.color }}
					>
						<div className="flex size-5 items-center justify-center rounded-full bg-white/20 text-[9px] font-bold text-white">
							{collaborator.name[0]}
						</div>
						<span className="shrink-0 text-[10px] font-medium text-white">
							{collaborator.name}
						</span>
						<span className="rounded bg-white/20 px-1 py-px text-[8px] text-white/80">
							{collaborator.role}
						</span>
					</div>
				</motion.div>
			))}
		</div>
	);
}

function FeatureCard({
	title,
	description,
	skeleton,
}: {
	title: string;
	description: string;
	skeleton: React.ReactNode;
}) {
	return (
		<div className="flex h-full flex-col justify-between bg-card p-10 first:rounded-l-2xl last:rounded-r-2xl">
			<div className="h-60 w-full overflow-visible rounded-md">{skeleton}</div>
			<div className="mt-4">
				<h3 className="text-base font-bold tracking-tight text-card-foreground">
					{title}
				</h3>
				<p className="mt-2 text-sm leading-relaxed tracking-tight text-muted-foreground">
					{description}
				</p>
			</div>
		</div>
	);
}

const comparisonRows: {
	feature: string;
	notebookLm: string | boolean;
	surfSense: string | boolean;
}[] = [
	{
		feature: "Sources per Notebook",
		notebookLm: "50-600",
		surfSense: "Unlimited",
	},
	{
		feature: "LLM Support",
		notebookLm: "Gemini only",
		surfSense: "100+ LLMs",
	},
	{
		feature: "Self-Hostable",
		notebookLm: false,
		surfSense: true,
	},
	{
		feature: "Open Source",
		notebookLm: false,
		surfSense: true,
	},
	{
		feature: "External Connectors",
		notebookLm: "Limited",
		surfSense: "27+",
	},
	{
		feature: "Desktop App",
		notebookLm: false,
		surfSense: true,
	},
	{
		feature: "Agentic Architecture",
		notebookLm: false,
		surfSense: true,
	},
];

function ComparisonStrip() {
	const ref = useRef(null);
	const isInView = useInView(ref, { once: true, margin: "-80px" });

	return (
		<motion.div
			ref={ref}
			initial={{ opacity: 0, y: 20 }}
			animate={isInView ? { opacity: 1, y: 0 } : {}}
			transition={{ duration: 0.5, delay: 0.1 }}
			className="mx-auto mt-12 w-full max-w-4xl overflow-hidden rounded-2xl bg-card shadow-sm ring-1 ring-border"
		>
			<div className="grid grid-cols-3 px-4 py-3 sm:px-6">
				<span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
					Feature
				</span>
				<span className="text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
					NotebookLM
				</span>
				<span className="text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">
					SurfSense
				</span>
			</div>

			<Separator />

			{comparisonRows.map((row, index) => (
				<motion.div
					key={row.feature}
					initial={{ opacity: 0, x: -10 }}
					animate={isInView ? { opacity: 1, x: 0 } : {}}
					transition={{ duration: 0.3, delay: 0.15 + index * 0.06 }}
				>
					<div className="grid grid-cols-3 items-center px-4 py-2.5 text-sm sm:px-6">
						<span className="font-medium text-card-foreground">
							{row.feature}
						</span>
						<span className="flex justify-center">
							{typeof row.notebookLm === "boolean" ? (
								row.notebookLm ? (
									<Check className="size-4 text-brand" />
								) : (
									<X className="size-4 text-muted-foreground/40" />
								)
							) : (
								<span className="text-muted-foreground">
									{row.notebookLm}
								</span>
							)}
						</span>
						<span className="flex justify-center">
							{typeof row.surfSense === "boolean" ? (
								row.surfSense ? (
									<Check className="size-4 text-brand" />
								) : (
									<X className="size-4 text-muted-foreground/40" />
								)
							) : (
								<Badge variant="secondary">{row.surfSense}</Badge>
							)}
						</span>
					</div>
					{index !== comparisonRows.length - 1 && (
						<Separator />
					)}
				</motion.div>
			))}
		</motion.div>
	);
}
