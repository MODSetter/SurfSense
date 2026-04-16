import { SquareArrowOutUpRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { AnonModel } from "@/contracts/types/anonymous-chat.types";
import { BACKEND_URL } from "@/lib/env-config";

export const metadata: Metadata = {
	title: "ChatGPT Free Online Without Login | Chat GPT No Login, Claude AI Free | SurfSense",
	description:
		"Use ChatGPT free online without login. Chat with GPT-4, Claude AI, Gemini and more for free. No sign-up required. Open source NotebookLM alternative with free AI chat and document Q&A.",
	keywords: [
		"chatgpt free",
		"chat gpt free",
		"free chatgpt",
		"free chat gpt",
		"chatgpt online",
		"chat gpt online",
		"online chatgpt",
		"chatgpt free online",
		"chatgpt online free",
		"chat gpt free online",
		"chatgpt no login",
		"chatgpt without login",
		"chat gpt login free",
		"chat gpt login",
		"free chatgpt without login",
		"free chatgpt no login",
		"ai chat no login",
		"ai chat without login",
		"claude ai without login",
		"claude no login",
		"chatgpt for free",
		"gpt chat free",
		"claude ai free",
		"claude free",
		"free claude ai",
		"free claude",
		"chatgpt alternative free",
		"free chatgpt alternative",
		"chatgpt free alternative",
		"free alternative to chatgpt",
		"alternative to chatgpt free",
		"ai like chatgpt",
		"sites like chatgpt",
		"free ai chatbot like chatgpt",
		"free ai chatbots like chatgpt",
		"apps like chatgpt for free",
		"best free alternative to chatgpt",
		"free ai apps",
		"ai with no restrictions",
		"notebooklm alternative",
	],
	alternates: {
		canonical: "https://surfsense.com/free",
	},
	openGraph: {
		title: "ChatGPT Free Online Without Login | Claude AI Free No Login | SurfSense",
		description:
			"Use ChatGPT free online without login. Chat with GPT-4, Claude AI, Gemini and 100+ AI models. Open source NotebookLM alternative.",
		url: "https://surfsense.com/free",
		siteName: "SurfSense",
		type: "website",
		images: [
			{
				url: "/og-image.png",
				width: 1200,
				height: 630,
				alt: "SurfSense - ChatGPT Free Online, Claude AI Free, No Login Required",
			},
		],
	},
	twitter: {
		card: "summary_large_image",
		title: "ChatGPT Free Online Without Login | Claude AI Free No Login | SurfSense",
		description:
			"Use ChatGPT free online without login. Chat with GPT-4, Claude AI, Gemini and more. No sign-up needed.",
		images: ["/og-image.png"],
	},
};

async function getModels(): Promise<AnonModel[]> {
	try {
		const res = await fetch(`${BACKEND_URL}/api/v1/public/anon-chat/models`, {
			next: { revalidate: 300 },
		});
		if (!res.ok) return [];
		return res.json();
	} catch {
		return [];
	}
}

const FAQ_ITEMS = [
	{
		question: "Can I use ChatGPT without login?",
		answer:
			"Yes. SurfSense lets you use ChatGPT without login or any sign-up. Just pick a model and start chatting. No email, no password, no account needed. You get 1 million free tokens to use across ChatGPT, Claude AI, Gemini, and other models.",
	},
	{
		question: "Is ChatGPT really free on SurfSense?",
		answer:
			"Yes. SurfSense gives you free access to ChatGPT (GPT-4), Claude AI, Gemini, and other models without login. You get 1 million free tokens across any model with no sign-up required.",
	},
	{
		question: "How do I use ChatGPT no login?",
		answer:
			"Go to any model page on SurfSense and start typing your message. There is no login wall, no account creation, and no verification step. ChatGPT no login works instantly in your browser.",
	},
	{
		question: "What AI models can I use for free without login?",
		answer:
			"SurfSense offers free access without login to models from OpenAI (GPT-4, GPT-4 Turbo), Anthropic (Claude 3, Claude free), Google (Gemini), DeepSeek, Mistral, Llama, and more. All available as a free ChatGPT alternative online with no login required.",
	},
	{
		question: "What happens after I use 1 million free tokens?",
		answer:
			"After your free tokens, create a free SurfSense account to unlock 5 million more. Premium model tokens can be purchased at $1 per million tokens. Non-premium models remain unlimited for registered users.",
	},
	{
		question: "Is Claude AI available without login?",
		answer:
			"Yes. You can use Claude AI free without login on SurfSense. Both Claude 3 and other Anthropic models are available with no sign-up, alongside ChatGPT and Gemini.",
	},
	{
		question: "How is SurfSense different from ChatGPT?",
		answer:
			"SurfSense is an open source NotebookLM alternative that gives you access to multiple AI models in one place without login. Unlike ChatGPT alone, SurfSense includes document Q&A with citations, integrations with Slack, Google Drive, Notion, and Confluence, plus team collaboration features.",
	},
	{
		question: "Is SurfSense a free ChatGPT alternative?",
		answer:
			"Yes. SurfSense is a free, open source alternative to ChatGPT that works without login. It gives you access to Claude AI free, Gemini, and other AI models alongside document Q&A with citations, team collaboration, and 30+ integrations.",
	},
	{
		question: "Is my data private when using free AI chat without login?",
		answer:
			"Anonymous chat sessions are not stored in any database. No account means no personal data collected. SurfSense is open source, so you can self-host for complete data control and privacy.",
	},
];

export default async function FreeHubPage() {
	const models = await getModels();
	const seoModels = models.filter((m) => m.seo_slug);

	return (
		<main className="min-h-screen pt-20">
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "CollectionPage",
					name: "ChatGPT Free Online Without Login - SurfSense",
					description:
						"Use ChatGPT, Claude AI, Gemini and more AI models free online without login or sign-up. Open source NotebookLM alternative with no login required.",
					url: "https://surfsense.com/free",
					isPartOf: { "@type": "WebSite", name: "SurfSense", url: "https://surfsense.com" },
					mainEntity: {
						"@type": "ItemList",
						numberOfItems: seoModels.length,
						itemListElement: seoModels.map((m, i) => ({
							"@type": "ListItem",
							position: i + 1,
							name: m.name,
							url: `https://surfsense.com/free/${m.seo_slug}`,
						})),
					},
				}}
			/>
			<FAQJsonLd questions={FAQ_ITEMS} />

			<article className="container mx-auto px-4 pb-20">
				<BreadcrumbNav
					items={[
						{ name: "Home", href: "/" },
						{ name: "Free AI Chat", href: "/free" },
					]}
				/>

				{/* Hero */}
				<section className="mt-8 text-center max-w-3xl mx-auto">
					<h1 className="text-4xl md:text-5xl font-bold tracking-tight">
						ChatGPT Free Online Without Login
					</h1>
					<p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto leading-relaxed">
						Use <strong>ChatGPT</strong>, <strong>Claude AI</strong>, <strong>Gemini</strong>, and
						other AI models free online without login. No sign-up, no email, no password. Pick a
						model and start chatting instantly.
					</p>
					<div className="flex flex-wrap items-center justify-center gap-3 mt-6">
						<Badge variant="secondary" className="px-3 py-1.5 text-sm">
							No login required
						</Badge>
						<Badge variant="secondary" className="px-3 py-1.5 text-sm">
							1M free tokens
						</Badge>
						<Badge variant="secondary" className="px-3 py-1.5 text-sm">
							{seoModels.length} AI models
						</Badge>
						<Badge variant="secondary" className="px-3 py-1.5 text-sm">
							Open source
						</Badge>
					</div>
				</section>

				<Separator className="my-12 max-w-4xl mx-auto" />

				{/* Model Table */}
				{seoModels.length > 0 ? (
					<section
						className="max-w-4xl mx-auto"
						aria-label="Free AI models available without login"
					>
						<h2 className="text-2xl font-bold mb-2">Free AI Models Available Without Login</h2>
						<p className="text-sm text-muted-foreground mb-6">
							All models below work without login or sign-up. Click any model to start a free AI
							chat instantly.
						</p>

						<div className="overflow-hidden rounded-lg border">
							<Table>
								<TableHeader>
									<TableRow>
										<TableHead className="w-[45%]">Model</TableHead>
										<TableHead>Provider</TableHead>
										<TableHead>Tier</TableHead>
										<TableHead className="text-right w-[100px]" />
									</TableRow>
								</TableHeader>
								<TableBody>
									{seoModels.map((model) => (
										<TableRow key={model.id}>
											<TableCell>
												<Link
													href={`/free/${model.seo_slug}`}
													className="group flex flex-col gap-0.5"
												>
													<span className="font-medium group-hover:underline">{model.name}</span>
													{model.description && (
														<span className="text-xs text-muted-foreground line-clamp-1">
															{model.description}
														</span>
													)}
												</Link>
											</TableCell>
											<TableCell>
												<Badge variant="outline">{model.provider}</Badge>
											</TableCell>
											<TableCell>
												{model.is_premium ? (
													<Badge className="bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300 border-0">
														Premium
													</Badge>
												) : (
													<Badge variant="secondary">Free</Badge>
												)}
											</TableCell>
											<TableCell className="text-right">
												<Button variant="ghost" size="sm" asChild>
													<Link href={`/free/${model.seo_slug}`}>
														Chat
														<SquareArrowOutUpRight className="size-3" />
													</Link>
												</Button>
											</TableCell>
										</TableRow>
									))}
								</TableBody>
							</Table>
						</div>
					</section>
				) : (
					<section className="mt-12 text-center max-w-4xl mx-auto">
						<p className="text-muted-foreground">
							No models are currently available. Please check back later.
						</p>
					</section>
				)}

				<Separator className="my-12 max-w-4xl mx-auto" />

				{/* Why SurfSense */}
				<section className="max-w-4xl mx-auto">
					<h2 className="text-2xl font-bold mb-6">
						Why Use SurfSense as Your Free ChatGPT Alternative
					</h2>
					<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
						<div className="rounded-lg border bg-card p-5">
							<h3 className="font-semibold mb-1.5">Multiple AI Models in One Place</h3>
							<p className="text-sm text-muted-foreground leading-relaxed">
								Access ChatGPT, Claude AI free, Gemini, DeepSeek, and more. Works like sites like
								ChatGPT but with all AI models available, not just GPT. A true free AI chatbot like
								ChatGPT and beyond.
							</p>
						</div>
						<div className="rounded-lg border bg-card p-5">
							<h3 className="font-semibold mb-1.5">No Login, No Sign-Up Required</h3>
							<p className="text-sm text-muted-foreground leading-relaxed">
								Start using ChatGPT free online immediately. No email, no password, no verification.
								Get ChatGPT no login access and Claude AI free access from one platform. AI with no
								restrictions on which model you can use.
							</p>
						</div>
						<div className="rounded-lg border bg-card p-5">
							<h3 className="font-semibold mb-1.5">Open Source NotebookLM Alternative</h3>
							<p className="text-sm text-muted-foreground leading-relaxed">
								SurfSense is a free, open source NotebookLM alternative with document Q&A and
								citations, integrations with Slack, Google Drive, Notion, and Confluence, plus team
								collaboration and self-hosting support.
							</p>
						</div>
					</div>
				</section>

				<Separator className="my-12 max-w-4xl mx-auto" />

				{/* CTA */}
				<section className="max-w-3xl mx-auto text-center">
					<h2 className="text-2xl font-bold mb-3">Want More Features?</h2>
					<p className="text-muted-foreground mb-6 leading-relaxed">
						Create a free SurfSense account to unlock 5 million tokens, document uploads with
						citations, team collaboration, and integrations with Slack, Google Drive, Notion, and
						30+ more tools.
					</p>
					<Button size="lg" asChild>
						<Link href="/register">Create Free Account</Link>
					</Button>
				</section>

				<Separator className="my-12 max-w-4xl mx-auto" />

				{/* FAQ */}
				<section className="max-w-3xl mx-auto">
					<h2 className="text-2xl font-bold text-center mb-8">Frequently Asked Questions</h2>
					<dl className="flex flex-col gap-4">
						{FAQ_ITEMS.map((item) => (
							<div key={item.question} className="rounded-lg border bg-card p-5">
								<dt className="font-medium text-sm">{item.question}</dt>
								<dd className="mt-2 text-sm text-muted-foreground leading-relaxed">
									{item.answer}
								</dd>
							</div>
						))}
					</dl>
				</section>

				{/* Internal links */}
				<nav aria-label="Related pages" className="mt-16 max-w-3xl mx-auto">
					<h2 className="text-lg font-semibold mb-3">Explore SurfSense</h2>
					<ul className="flex flex-wrap gap-2">
						<li>
							<Button variant="outline" size="sm" asChild>
								<Link href="/pricing">Pricing</Link>
							</Button>
						</li>
						<li>
							<Button variant="outline" size="sm" asChild>
								<Link href="/docs">Documentation</Link>
							</Button>
						</li>
						<li>
							<Button variant="outline" size="sm" asChild>
								<Link href="/blog">Blog</Link>
							</Button>
						</li>
						<li>
							<Button variant="outline" size="sm" asChild>
								<Link href="/register">Sign Up Free</Link>
							</Button>
						</li>
					</ul>
				</nav>
			</article>
		</main>
	);
}
