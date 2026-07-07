"use client";
import { IconPlus } from "@tabler/icons-react";
import { AnimatePresence, motion } from "motion/react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import { Pricing } from "@/components/pricing";
import { FAQJsonLd } from "@/components/seo/json-ld";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const demoPlans = [
	{
		name: "FREE",
		price: "0",
		yearlyPrice: "0",
		period: "",
		billingText: "Open source. Run it on your own infrastructure",
		features: [
			"Full platform: connectors, agents, automations, and the MCP server",
			"Unlimited scraping and crawling, you control billing",
			"Bring your own keys for any model provider",
			"Keep competitive research on your own infrastructure",
			"Community support on Discord",
		],
		description: "",
		buttonText: "View on GitHub",
		href: "https://github.com/MODSetter/SurfSense",
		isPopular: false,
	},
	{
		name: "PAY AS YOU GO",
		price: "5",
		yearlyPrice: "5",
		period: "to start",
		billingText: "Your first $5 of credit is free. No subscription, ever",
		features: [
			"$5 of free credit to start, one balance for everything",
			"Platform connectors: Reddit, YouTube, Google Maps, Google Search, and the open web",
			"Call every connector as a REST API with your key or through the MCP server",
			"Pay per item returned and per page crawled. Failed calls are never billed",
			"Premium models like GPT-5.5, Claude Sonnet 5, Gemini 3.1 Pro billed at provider cost",
			"Scheduled and event-triggered agents for briefs, alerts, and monitoring",
			"Write results back to Notion, Slack, Linear, and Jira",
			"Add credit any time. $1 buys $1 of credit, with optional automatic refills",
			"Priority support on Discord",
		],
		description: "",
		buttonText: "Get Started",
		href: "/login",
		isPopular: true,
	},
	{
		name: "ENTERPRISE",
		price: "Contact Us",
		yearlyPrice: "Contact Us",
		period: "",
		billingText: "",
		features: [
			"Everything in Pay As You Go",
			"Custom connectors and agent workflows",
			"On-prem or VPC deployment",
			"Audit logs and compliance",
			"SSO, OIDC & SAML",
			"White-glove setup and deployment",
			"Monthly managed updates and maintenance",
			"SLA commitments",
			"Dedicated support",
		],
		description: "Customized setup for large organizations",
		buttonText: "Contact Sales",
		href: "/contact",
		isPopular: false,
	},
];

interface FAQItem {
	question: string;
	answer: string;
}

interface FAQSection {
	title: string;
	items: FAQItem[];
}

const faqData: FAQSection[] = [
	{
		title: "Credits & Pay As You Go",
		items: [
			{
				question: "What are credits in SurfSense?",
				answer:
					"Credits are a single prepaid balance shown in dollars that powers everything in SurfSense: platform connector calls, web crawls, document processing, and premium AI models. New accounts start with $5 of free credit. There is one number to watch, and it only moves when you actually use the product.",
			},
			{
				question: "How does Pay As You Go work?",
				answer:
					"There is no monthly subscription. Start with $5 of free credit, and when you need more, add any amount. $1 buys exactly $1 of credit, added to your balance immediately. You can enable automatic refills when your balance runs low, and turn them off any time."
			},
			{
				question: "What happens if I run out of credit?",
				answer:
					"SurfSense checks your balance before every billable call, so your wallet can never go negative. When credit runs out, connector calls, crawls, premium model requests, and document processing pause until you top up. Free models and connectors that do not consume credit keep working.",
			},
			{
				question: "Do failed scrapes or crawls cost anything?",
				answer:
					"No. Platform connectors bill per item actually returned, and web crawls bill per page successfully fetched. A request that errors, times out, or comes back empty is not charged. You pay for data you receive, not for attempts.",
			},
		],
	},
	{
		title: "Connector & Scraping Pricing",
		items: [
			{
				question: "How are platform connectors billed?",
				answer:
					"Each platform connector meters per item returned: a Reddit post or comment, a Google Search results page, a Google Maps place or review, a YouTube video or comment. Rates are fractions of a cent per item and are debited from your credit balance after the call succeeds, so your $5 of free credit covers hundreds of items.",
			},
			{
				question: "How much does web crawling cost?",
				answer:
					"Web crawls are billed per successfully fetched page at a fraction of a cent, so $1 of credit covers hundreds of pages. Pages that fail to load are never charged. Crawled pages can feed your agents directly or be indexed into your knowledge base for later questions.",
			},
			{
				question: "Does the REST API cost the same as the MCP server?",
				answer:
					"Yes. Whether your own app calls a connector with your SurfSense API key or your agent calls it as a tool through the MCP server, it is the same endpoint, the same per-item rate, and the same credit balance. There is no separate API plan or seat fee.",
			},
			{
				question: "What can I add to the knowledge base?",
				answer:
					"You can upload files directly or sync documents from Google Drive, OneDrive, and Dropbox. Crawled pages can also be indexed for later questions. Document files are billed per page processed; connecting the drives themselves costs nothing.",
			},
		],
	},
	{
		title: "Premium AI, Agents & Automations",
		items: [
			{
				question: "How is credit used for premium AI?",
				answer:
					"The same balance pays for premium AI models like GPT-5.5, Claude Sonnet 5, and Gemini 3.1 Pro, plus over 100 more via OpenRouter, and for premium features such as image generation, podcasts, and video presentations. Each request debits the actual USD provider cost, so cheaper models bill proportionally less.",
			},
			{
				question: "Do agents and automations cost extra?",
				answer:
					"No. There is no add-on fee for agents or automations. A scheduled competitor brief or an event-triggered alert draws from the same credit balance: connector items and crawled pages at their per-unit rates, and model usage at provider cost. A workflow that uses free models and no scraping costs nothing.",
			},
			{
				question: "What can the agents actually do?",
				answer:
					"You describe the job in plain English and SurfSense sets up the agent, no code needed. Agents can watch competitor pricing pages, track brand mentions on Reddit and YouTube, monitor Google rankings and Maps reviews, then turn what they find into briefs and alerts, and write results back to Notion, Slack, Linear, and Jira.",
			},
		],
	},
	{
		title: "Documents & Knowledge Base",
		items: [
			{
				question: "How much does document processing cost?",
				answer:
					"Document processing is billed per page from your credit balance. Basic mode costs $0.001 per page and Premium mode costs $0.01 per page, with Premium using advanced extraction for complex financial, medical, and legal layouts. Pages in Word, PowerPoint, and Excel files are estimated automatically, and every file uses at least 1 page.",
			},
			{
				question: "Which file types use credit?",
				answer:
					"Only document files that need processing: PDFs, Word documents, presentations, spreadsheets, ebooks, and images. Plain text, code, Markdown, CSV, HTML, audio, and video files are indexed free. Duplicate documents are detected automatically and never charged twice.",
			},
			{
				question: "If I delete a document, do I get my credit back?",
				answer:
					"No. Deleting a document removes it from your knowledge base, but the credit it used is not refunded. Credit tracks your total usage over time, not how much is currently stored, so once credit is spent it stays spent even if you later remove the document.",
			},
		],
	},
	{
		title: "Self-Hosting",
		items: [
			{
				question: "Is the self-hosted version really free and unlimited?",
				answer:
					"Yes. SurfSense is open source, and the default self-hosted configuration ships with all credit billing switched off. Scraping, crawling, document processing, and agent runs are limited only by your own infrastructure and the model provider keys you bring.",
			},
			{
				question: "What is the difference between self-hosted and cloud?",
				answer:
					"Both run the same platform: connectors, agents, automations, and the MCP server. Cloud is zero-setup with managed infrastructure and metered pay-as-you-go credit. Self-hosted runs on your machines with your own model keys, keeps competitive research fully in-house, and leaves billing under your control.",
			},
		],
	},
];

const GridLineHorizontal = ({ className, offset }: { className?: string; offset?: string }) => {
	return (
		<div
			style={
				{
					"--background": "#ffffff",
					"--color": "rgba(0, 0, 0, 0.2)",
					"--height": "1px",
					"--width": "5px",
					"--fade-stop": "90%",
					"--offset": offset || "200px",
					"--color-dark": "rgba(255, 255, 255, 0.2)",
					maskComposite: "exclude",
				} as React.CSSProperties
			}
			className={cn(
				"[--background:var(--color-neutral-200)] [--color:var(--color-neutral-400)] dark:[--background:var(--color-neutral-800)] dark:[--color:var(--color-neutral-600)]",
				"absolute left-[calc(var(--offset)/2*-1)] h-(--height) w-[calc(100%+var(--offset))]",
				"bg-[linear-gradient(to_right,var(--color),var(--color)_50%,transparent_0,transparent)]",
				"bg-size-[var(--width)_var(--height)]",
				"[mask:linear-gradient(to_left,var(--background)_var(--fade-stop),transparent),linear-gradient(to_right,var(--background)_var(--fade-stop),transparent),linear-gradient(black,black)]",
				"mask-exclude",
				"z-30",
				"dark:bg-[linear-gradient(to_right,var(--color-dark),var(--color-dark)_50%,transparent_0,transparent)]",
				className
			)}
		/>
	);
};

const GridLineVertical = ({ className, offset }: { className?: string; offset?: string }) => {
	return (
		<div
			style={
				{
					"--background": "#ffffff",
					"--color": "rgba(0, 0, 0, 0.2)",
					"--height": "5px",
					"--width": "1px",
					"--fade-stop": "90%",
					"--offset": offset || "150px",
					"--color-dark": "rgba(255, 255, 255, 0.2)",
					maskComposite: "exclude",
				} as React.CSSProperties
			}
			className={cn(
				"absolute top-[calc(var(--offset)/2*-1)] h-[calc(100%+var(--offset))] w-(--width)",
				"bg-[linear-gradient(to_bottom,var(--color),var(--color)_50%,transparent_0,transparent)]",
				"bg-size-[var(--width)_var(--height)]",
				"[mask:linear-gradient(to_top,var(--background)_var(--fade-stop),transparent),linear-gradient(to_bottom,var(--background)_var(--fade-stop),transparent),linear-gradient(black,black)]",
				"mask-exclude",
				"z-30",
				"dark:bg-[linear-gradient(to_bottom,var(--color-dark),var(--color-dark)_50%,transparent_0,transparent)]",
				className
			)}
		/>
	);
};

function PricingFAQ() {
	const [activeId, setActiveId] = useState<string | null>(null);
	const containerRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		function handleClickOutside(event: MouseEvent) {
			if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
				setActiveId(null);
			}
		}

		document.addEventListener("mousedown", handleClickOutside);
		return () => document.removeEventListener("mousedown", handleClickOutside);
	}, []);

	const toggleQuestion = (id: string) => {
		setActiveId(activeId === id ? null : id);
	};

	return (
		<div className="mx-auto w-full max-w-4xl overflow-hidden px-4 py-20 md:px-8 md:py-32">
			<FAQJsonLd questions={faqData.flatMap((section) => section.items)} />
			<div className="text-center">
				<h2 className="text-4xl font-bold tracking-tight sm:text-5xl">
					Frequently Asked Questions
				</h2>
				<p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
					Everything you need to know about SurfSense credits and billing. Can&apos;t find what you
					need? Reach out at{" "}
					<a href="mailto:rohan@surfsense.com" className="text-blue-500 underline">
						rohan@surfsense.com
					</a>
				</p>
			</div>

			<div ref={containerRef} className="relative mt-16 flex w-full flex-col gap-12 px-4 md:px-8">
				{faqData.map((section) => (
					<div key={`${section.title}faq`}>
						<h3 className="mb-6 text-lg font-medium text-neutral-800 dark:text-neutral-200">
							{section.title}
						</h3>
						<div className="flex flex-col gap-3">
							{section.items.map((item, index) => {
								const id = `${section.title}-${index}`;
								const isActive = activeId === id;

								return (
									<div
										key={`${id}faq-item`}
										className={cn(
											"relative rounded-lg transition-all duration-200",
											isActive
												? "bg-white shadow-sm ring-1 shadow-black/10 ring-black/10 dark:bg-neutral-900 dark:shadow-white/5 dark:ring-white/10"
												: "hover:bg-neutral-50 dark:hover:bg-neutral-900"
										)}
									>
										{isActive && (
											<div className="absolute inset-0">
												<GridLineHorizontal className="-top-[2px]" offset="100px" />
												<GridLineHorizontal className="-bottom-[2px]" offset="100px" />
												<GridLineVertical className="-left-[2px]" offset="100px" />
												<GridLineVertical className="-right-[2px] left-auto" offset="100px" />
											</div>
										)}
										<Button
											variant="ghost"
											type="button"
											onClick={() => toggleQuestion(id)}
											className="h-auto w-full justify-between rounded-lg px-4 py-4 text-left hover:bg-transparent"
										>
											<span className="text-sm font-medium text-neutral-700 md:text-base dark:text-neutral-300">
												{item.question}
											</span>
											<motion.div
												animate={{ rotate: isActive ? 45 : 0 }}
												transition={{ duration: 0.2 }}
												className="ml-4 shrink-0"
											>
												<IconPlus className="size-5 text-neutral-500 dark:text-neutral-400" />
											</motion.div>
										</Button>
										<AnimatePresence initial={false}>
											{isActive && (
												<motion.div
													initial={{ height: 0, opacity: 0 }}
													animate={{ height: "auto", opacity: 1 }}
													exit={{ height: 0, opacity: 0 }}
													transition={{ duration: 0.15, ease: "easeInOut" }}
													className="relative"
												>
													<p className="max-w-[90%] px-4 pb-4 text-sm text-neutral-600 dark:text-neutral-400">
														{item.answer}
													</p>
												</motion.div>
											)}
										</AnimatePresence>
									</div>
								);
							})}
						</div>
					</div>
				))}
			</div>
		</div>
	);
}

function PricingBasic() {
	return (
		<>
			<Pricing
				plans={demoPlans}
				title="SurfSense Pricing"
				description="Give your agents competitive intelligence. Self-host for free, or start with $5 of credit and pay as you go. No subscriptions."
			/>
			<PricingFAQ />
		</>
	);
}

export default PricingBasic;
