"use client";

import Link from "next/link";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/components/ui/cn";
import { ArrowRightIcon } from "@/components/ui/icons";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ShownUseCase } from "./shown-use-cases";
import { UseCaseVideo } from "./use-case-video";

/**
 * Use-case videos with their steps: a tab per use case, or the one panel when there is
 * one. Only the open tab's video is on the page, so switching tabs plays the new one.
 * The headings stay `<p>`s: the pages' H2s carry their keywords in a fixed order.
 */

function UseCasePanel({ useCase, placement }: { useCase: ShownUseCase; placement: string }) {
	return (
		<div className="grid items-center gap-8 lg:grid-cols-12 lg:gap-12">
			<figure className="m-0 lg:col-span-8">
				<UseCaseVideo
					slug={useCase.slug}
					src={useCase.src}
					poster={useCase.poster}
					title={useCase.title}
					placement={placement}
				/>
				<figcaption className={cn(siteText.body, "mt-3 text-sm")}>{useCase.caption}</figcaption>
			</figure>

			<div className="lg:col-span-4">
				<p className={siteText.h3}>{useCase.heading}</p>
				<ol className="m-0 mt-5 flex list-none flex-col gap-4 p-0">
					{useCase.steps.map((step, index) => (
						<li key={step} className="flex gap-3">
							<span
								aria-hidden="true"
								className="grid size-7 shrink-0 place-items-center rounded-full bg-foreground font-mono text-xs text-background"
							>
								{index + 1}
							</span>
							<span className={cn(siteText.body, "pt-0.5 text-sm")}>{step}</span>
						</li>
					))}
				</ol>
				<p className="mt-6">
					<Link className={siteText.forward} href={useCase.guideHref}>
						Read the full guide <ArrowRightIcon aria-hidden="true" className="size-4" />
					</Link>
				</p>
			</div>
		</div>
	);
}

export function UseCaseTabs({
	useCases,
	placement,
}: {
	useCases: ShownUseCase[];
	placement: string;
}) {
	const [first] = useCases;
	if (!first) return null;
	if (useCases.length === 1) return <UseCasePanel useCase={first} placement={placement} />;
	return (
		<Tabs defaultValue={first.slug}>
			<TabsList
				aria-label="Use-case videos"
				className="flex h-auto flex-wrap justify-center gap-2 bg-transparent p-0"
			>
				{useCases.map((useCase) => (
					<TabsTrigger
						key={useCase.slug}
						value={useCase.slug}
						className="rounded-full border border-border bg-card px-4 py-2 text-sm font-medium text-muted-foreground shadow-xs data-[state=active]:border-foreground data-[state=active]:bg-foreground data-[state=active]:text-background data-[state=active]:shadow-xs data-[state=inactive]:hover:text-foreground"
					>
						{useCase.label}
					</TabsTrigger>
				))}
			</TabsList>
			{useCases.map((useCase) => (
				<TabsContent key={useCase.slug} value={useCase.slug} className="mt-8 lg:mt-10">
					<UseCasePanel useCase={useCase} placement={placement} />
				</TabsContent>
			))}
		</Tabs>
	);
}
