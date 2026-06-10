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
		billingText: "$5 of credit included to start",
		features: [
			"Self Hostable",
			"$5 of credit included to start",
			"One credit balance for document processing and premium AI features",
			"Includes access to OpenAI text, audio and image models",
			"AI automations and agents: scheduled and event-triggered workflows",
			"Desktop app: Quick, General and Screenshot Assist plus local folder sync",
			"Realtime Collaborative Group Chats with teammates",
			"Community support on Discord",
		],
		description: "",
		buttonText: "Get Started",
		href: "/login",
		isPopular: false,
	},
	{
		name: "PAY AS YOU GO",
		price: "1",
		yearlyPrice: "1",
		period: "pack",
		billingText: "No subscription, buy only when you need more",
		features: [
			"Everything in Free",
			"Buy credit in $1 packs — $1 buys $1 of credit, with optional auto-reload",
			"Use premium AI models like GPT-5.4, Claude Sonnet 4.6, Gemini 2.5 Pro & 100+ more via OpenRouter",
			"Connector write-back to Notion, Slack, Linear & Jira",
			"Priority support on Discord",
		],
		description: "",
		buttonText: "Get Started",
		href: "/login",
		isPopular: false,
	},
	{
		name: "ENTERPRISE",
		price: "Contact Us",
		yearlyPrice: "Contact Us",
		period: "",
		billingText: "",
		features: [
			"Everything in Pay As You Go",
			"Custom automation and agent workflows",
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
		title: "Credits & Document Billing",
		items: [
			{
				question: "What are credits in SurfSense?",
				answer:
					"Credits are a single prepaid balance shown in dollars that powers everything in SurfSense — both document processing and premium AI features. New accounts start with $5 of credit. Your balance goes down as you use the product and back up when you top up or earn more, so there's just one number to keep an eye on.",
			},
			{
				question: "How much does document processing cost?",
				answer:
					"Document processing is billed per page out of your credit balance. For PDFs, one page equals one real PDF page; for other document types like Word, PowerPoint, and Excel files, pages are automatically estimated. Basic mode costs $0.001 per page and Premium mode costs $0.01 per page. Premium processing uses advanced extraction optimized for complex financial, medical, and legal documents with intricate tables and layouts. Every file uses at least 1 page.",
			},
			{
				question: "How does the Pay As You Go plan work?",
				answer:
					"There's no monthly subscription. When you need more credit, simply buy $1 packs — $1 buys exactly $1 of credit. Purchased credit is added to your balance immediately so you can keep working right away. You only pay when you actually need more, and you can enable auto-reload to top up automatically.",
			},
			{
				question: "What happens if I run out of credit?",
				answer:
					"SurfSense checks your remaining credit before processing each file. If you don't have enough, the upload is paused and you'll be notified so you can buy more credit and continue. For cloud connector syncs, a small overage may be allowed so your sync doesn't partially fail.",
			},
			{
				question: "If I delete a document, do I get my credit back?",
				answer:
					"No. Deleting a document removes it from your knowledge base, but the credit it used is not refunded. Credit tracks your total usage over time, not how much is currently stored, so be mindful of what you index. Once credit is spent, it's spent even if you later remove the document.",
			},
		],
	},
	{
		title: "File Types & Connectors",
		items: [
			{
				question: "Which file types use credit?",
				answer:
					"Credit is only used for document files that need processing, including PDFs, Word documents (DOC, DOCX, ODT, RTF), presentations (PPT, PPTX, ODP), spreadsheets (XLS, XLSX, ODS), ebooks (EPUB), and images (JPG, PNG, TIFF, WebP, BMP). Plain text files, code files, Markdown, CSV, TSV, HTML, audio, and video files do not consume any credit.",
			},
			{
				question: "How is credit consumed for documents?",
				answer:
					"Credit is deducted whenever a document file is successfully indexed into your knowledge base, whether through direct uploads or file-based connector syncs (Google Drive, OneDrive, Dropbox, Local Folder). In Basic mode each page costs $0.001; in Premium mode each page costs $0.01. SurfSense checks your remaining credit before processing and only charges you after the file is indexed. Duplicate documents are automatically detected and won't cost you extra.",
			},
			{
				question: "Do connectors like Slack, Notion, or Gmail use credit?",
				answer:
					"No. Connectors that work with structured text data like Slack, Discord, Notion, Confluence, Jira, Linear, ClickUp, GitHub, Gmail, Google Calendar, Microsoft Teams, Airtable, Elasticsearch, Web Crawler, BookStack, Obsidian, and Luma do not use credit at all. Document-processing charges only apply to file-based connectors such as Google Drive, OneDrive, Dropbox, and Local Folder syncs.",
			},
		],
	},
	{
		title: "Premium AI & Credit",
		items: [
			{
				question: "How is credit used for premium AI?",
				answer:
					"The same credit balance pays for paid AI usage in SurfSense, including premium AI models like GPT-5.4, Claude Sonnet 4.6, and Gemini 2.5 Pro, plus premium AI features such as image generation, podcasts, and video presentations when they use paid models. Each request debits the actual USD provider cost, so cheaper and more expensive models bill proportionally.",
			},
			{
				question: "How much credit do I get for free?",
				answer:
					"Every registered SurfSense account starts with $5 of credit at no cost. Anonymous users (no login) get 500,000 free tokens across free models before creating an account. Once your included credit runs out, you can top up at any time or earn more by completing tasks.",
			},
			{
				question: "How does buying credit work?",
				answer:
					"Top-ups are pay as you go, with no subscription. $1 buys $1 of credit, and your balance is spent at provider cost. Purchased credit is added to your account immediately, and you can buy up to $100 at a time. Enable auto-reload to top up automatically when your balance runs low.",
			},
			{
				question: "Is there a separate balance for documents and AI?",
				answer:
					"No. SurfSense uses one unified credit balance for everything — document indexing, file-based connector processing, premium model chats, and premium AI generation features all draw from the same wallet. Premium document processing mode simply costs more per page ($0.01 vs $0.001), but it's the same credit.",
			},
			{
				question: "What happens if I run out of credit?",
				answer:
					"When your credit balance runs low, you'll see a warning. Once you run out, paid model requests, premium AI features, and document processing are paused until you top up. You can still use non-premium models and features that do not consume credit.",
			},
		],
	},
	{
		title: "Automations & Agents",
		items: [
			{
				question: "What can AI automations and agents do?",
				answer:
					"AI automations let you run agents on your knowledge base without writing code. You can schedule recurring workflows like daily briefs, weekly status reports, and competitor analysis, or trigger an agent the moment a document lands in a folder. Agents can read across your connected tools, generate summaries and reports, and write results back to Notion, Slack, Linear, and Jira.",
			},
			{
				question: "Do automations and agents cost extra?",
				answer:
					"No. There is no separate subscription or add-on fee for automations. Agents draw from the same unified credit balance as the rest of SurfSense. Indexing documents and premium AI model usage during a workflow both consume credit at provider cost. If a workflow only uses free models and indexes no documents, it does not touch your credit.",
			},
			{
				question: "How do event-triggered automations work?",
				answer:
					"Event-triggered automations fire when something happens in your knowledge base, most commonly when a new document enters a folder you are watching. For example, when a PDF lands in your Research folder you can auto-generate a cited summary, or when an invoice is uploaded you can extract the vendor, total, and due date. The agent runs automatically and can post the result to your connected tools.",
			},
			{
				question: "Can I build an automation without code?",
				answer:
					"Yes. You can describe the workflow automation you want in plain English in chat, and SurfSense builds the automation for you. For example, ask it to email you a summary of new Notion pages each morning, or post a weekly research digest to Slack, and it sets up the scheduled or event-triggered agent without any code.",
			},
		],
	},
	{
		title: "Self-Hosting",
		items: [
			{
				question: "Can I self-host SurfSense with unlimited usage?",
				answer:
					"Yes! When self-hosting, you have full control over billing. The default self-hosted setup leaves document-processing credit billing off and gives you effectively unlimited credit, so you can index as much data and use as many AI queries as your infrastructure supports.",
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
					Everything you need to know about SurfSense credits and billing.
					Can&apos;t find what you need? Reach out at{" "}
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
				description="Start free with $5 of credit. Run AI automations and agents, and pay as you go."
			/>
			<PricingFAQ />
		</>
	);
}

export default PricingBasic;
