"use client";
import React, { useRef, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconPlus } from "@tabler/icons-react";
import { Pricing } from "@/components/pricing";
import { cn } from "@/lib/utils";

const demoPlans = [
	{
		name: "FREE",
		price: "0",
		yearlyPrice: "0",
		period: "",
		billingText: "500 pages included",
		features: [
			"Self Hostable",
			"500 pages included to start",
			"Earn up to 3,000+ bonus pages for free",
			"Includes access to OpenAI text, audio and image models",
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
		period: "1,000 pages",
		billingText: "No subscription, buy only when you need more",
		features: [
			"Everything in Free",
			"Buy 1,000-page packs at $1 each",
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
		title: "Pages & Billing",
		items: [
			{
				question: "What exactly is a \"page\" in SurfSense?",
				answer:
					"A page is a simple billing unit that measures how much content you add to your knowledge base. For PDFs, one page equals one real PDF page. For other document types like Word, PowerPoint, and Excel files, pages are automatically estimated based on the file. Every file uses at least 1 page.",
			},
			{
				question: "How does the Pay As You Go plan work?",
				answer:
					"There's no monthly subscription. When you need more pages, simply purchase 1,000-page packs at $1 each. Purchased pages are added to your account immediately so you can keep indexing right away. You only pay when you actually need more.",
			},
			{
				question: "What happens if I run out of pages?",
				answer:
					"SurfSense checks your remaining pages before processing each file. If you don't have enough, the upload is paused and you'll be notified. You can purchase additional page packs at any time to continue. For cloud connector syncs, a small overage may be allowed so your sync doesn't partially fail.",
			},
			{
				question: "If I delete a document, do I get my pages back?",
				answer:
					"No. Deleting a document removes it from your knowledge base, but the pages it used are not refunded. Pages track your total usage over time, not how much is currently stored. So be mindful of what you index. Once pages are spent, they're spent even if you later remove the document.",
			},
		],
	},
	{
		title: "File Types & Connectors",
		items: [
			{
				question: "Which file types count toward my page limit?",
				answer:
					"Page limits only apply to document files that need processing, including PDFs, Word documents (DOC, DOCX, ODT, RTF), presentations (PPT, PPTX, ODP), spreadsheets (XLS, XLSX, ODS), ebooks (EPUB), and images (JPG, PNG, TIFF, WebP, BMP). Plain text files, code files, Markdown, CSV, TSV, HTML, audio, and video files do not consume any pages.",
			},
			{
				question: "How are pages consumed?",
				answer:
					"Pages are deducted whenever a document file is successfully indexed into your knowledge base, whether through direct uploads or file-based connector syncs (Google Drive, OneDrive, Dropbox, Local Folder). SurfSense checks your remaining pages before processing and only charges you after the file is indexed. Duplicate documents are automatically detected and won't cost you extra pages.",
			},
			{
				question: "Do connectors like Slack, Notion, or Gmail use pages?",
				answer:
					"No. Connectors that work with structured text data like Slack, Discord, Notion, Confluence, Jira, Linear, ClickUp, GitHub, Gmail, Google Calendar, Microsoft Teams, Airtable, Elasticsearch, Web Crawler, BookStack, Obsidian, and Luma do not use pages at all. Page limits only apply to file-based connectors that need document processing, such as Google Drive, OneDrive, Dropbox, and Local Folder syncs.",
			},
		],
	},
	{
		title: "Self-Hosting",
		items: [
			{
				question: "Can I self-host SurfSense with unlimited pages?",
				answer:
					"Yes! When self-hosting, you have full control over your page limits. The default self-hosted setup gives you effectively unlimited pages, so you can index as much data as your infrastructure supports.",
			},
		],
	},
];

const GridLineHorizontal = ({
	className,
	offset,
}: {
	className?: string;
	offset?: string;
}) => {
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
				className,
			)}
		/>
	);
};

const GridLineVertical = ({
	className,
	offset,
}: {
	className?: string;
	offset?: string;
}) => {
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
				className,
			)}
		/>
	);
};

function PricingFAQ() {
	const [activeId, setActiveId] = useState<string | null>(null);
	const containerRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		function handleClickOutside(event: MouseEvent) {
			if (
				containerRef.current &&
				!containerRef.current.contains(event.target as Node)
			) {
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
			<div className="text-center">
				<h2 className="text-4xl font-bold tracking-tight sm:text-5xl">
					Frequently Asked Questions
				</h2>
				<p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
					Everything you need to know about SurfSense pages and billing.
					Can&apos;t find what you need? Reach out at{" "}
					<a
						href="mailto:rohan@surfsense.com"
						className="text-blue-500 underline"
					>
						rohan@surfsense.com
					</a>
				</p>
			</div>

			<div
				ref={containerRef}
				className="relative mt-16 flex w-full flex-col gap-12 px-4 md:px-8"
			>
				{faqData.map((section) => (
					<div key={section.title + "faq"}>
						<h3 className="mb-6 text-lg font-medium text-neutral-800 dark:text-neutral-200">
							{section.title}
						</h3>
						<div className="flex flex-col gap-3">
							{section.items.map((item, index) => {
								const id = `${section.title}-${index}`;
								const isActive = activeId === id;

								return (
									<div
										key={id + "faq-item"}
										className={cn(
											"relative rounded-lg transition-all duration-200",
											isActive
												? "bg-white shadow-sm ring-1 shadow-black/10 ring-black/10 dark:bg-neutral-900 dark:shadow-white/5 dark:ring-white/10"
												: "hover:bg-neutral-50 dark:hover:bg-neutral-900",
										)}
									>
										{isActive && (
											<div className="absolute inset-0">
												<GridLineHorizontal
													className="-top-[2px]"
													offset="100px"
												/>
												<GridLineHorizontal
													className="-bottom-[2px]"
													offset="100px"
												/>
												<GridLineVertical
													className="-left-[2px]"
													offset="100px"
												/>
												<GridLineVertical
													className="-right-[2px] left-auto"
													offset="100px"
												/>
											</div>
										)}
										<button
											onClick={() => toggleQuestion(id)}
											className="flex w-full items-center justify-between px-4 py-4 text-left"
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
										</button>
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
				description="Start free with 500 pages and pay as you go."
			/>
			<PricingFAQ />
		</>
	);
}

export default PricingBasic;
