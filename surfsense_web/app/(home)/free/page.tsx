import type { Metadata } from "next";
import Link from "next/link";
import { HomeButton } from "@/components/homepage/home/home-button";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { Badge } from "@/components/ui/badge";
import { LinkSquare02Icon } from "@/components/ui/icons";
import { ACCESS_LABEL, FREE_MODELS } from "@/lib/free-models";

/**
 * Rendered in the site design: the palette, ruled column, navigation and footer
 * all come from `app/(home)/layout.tsx`, and every style resolves from
 * `app/(home)/home.css`. Listed in `SITE_DESIGN_ROUTES` in
 * `components/site/site-shell.tsx`.
 *
 * The copy, metadata, keyword set and structured data are the ones this page
 * already ranks on and are left alone.
 *
 * The catalog, however, no longer comes from the hosted anon-chat endpoint —
 * that service is closed. Rows are a static, search-picked list in
 * `lib/free-models.ts`, and each one leads to `/free/[model_slug]`, which is now
 * the page that hands the visitor to the desktop app. The two columns that
 * described the old service (a Free/Premium tier, a "Chat" action) describe how
 * the app runs the model instead, because that is what the new data supports.
 */

export const metadata: Metadata = {
	title: "Free AI Chat, No Login Required | SurfSense",
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
		canonical: "https://www.surfsense.com/free",
	},
	openGraph: {
		title: "Free AI Chat, No Login Required | SurfSense",
		description:
			"Use ChatGPT free online without login. Chat with GPT-4, Claude AI, Gemini and 100+ AI models. Open source NotebookLM alternative.",
		url: "https://www.surfsense.com/free",
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
		title: "Free AI Chat, No Login Required | SurfSense",
		description:
			"Use ChatGPT free online without login. Chat with GPT-4, Claude AI, Gemini and more. No sign-up needed.",
		images: ["/og-image.png"],
	},
};

const FAQ_ITEMS = [
	{
		question: "Can I use ChatGPT without login?",
		answer:
			"Yes. SurfSense lets you use ChatGPT without login or any sign-up. Just pick a model and start chatting. No email, no password, no account needed. You get 500,000 free tokens to use across ChatGPT, Claude AI, Gemini, and other models.",
	},
	{
		question: "Is ChatGPT really free on SurfSense?",
		answer:
			"Yes. SurfSense gives you free access to ChatGPT (GPT-4), Claude AI, Gemini, and other models without login. You get 500,000 free tokens across any model with no sign-up required.",
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
		question: "What happens after I use my free tokens?",
		answer:
			"After your free tokens, create a free SurfSense account to unlock $5 of premium credit. Additional credit can be topped up at $1 for $1 of credit, billed at the actual provider cost. Non-premium models remain unlimited for registered users.",
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

export default function FreeHubPage() {
	return (
		<>
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "CollectionPage",
					name: "ChatGPT Free Online Without Login - SurfSense",
					description:
						"Use ChatGPT, Claude AI, Gemini and more AI models free online without login or sign-up. Open source NotebookLM alternative with no login required.",
					url: "https://www.surfsense.com/free",
					isPartOf: { "@type": "WebSite", name: "SurfSense", url: "https://www.surfsense.com" },
					mainEntity: {
						"@type": "ItemList",
						numberOfItems: FREE_MODELS.length,
						itemListElement: FREE_MODELS.map((model, i) => ({
							"@type": "ListItem",
							position: i + 1,
							name: model.name,
							url: `https://www.surfsense.com/free/${model.slug}`,
						})),
					},
				}}
			/>
			<FAQJsonLd questions={FAQ_ITEMS} />

			{/* Hero */}
			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-4xl text-center">
					<h1 className="ss-home-display">ChatGPT Free Online Without Login</h1>
					<p className="ss-home-lede mx-auto mt-8 max-w-2xl">
						Use <strong>ChatGPT</strong>, <strong>Claude AI</strong>, <strong>Gemini</strong>, and
						other AI models free online without login. No sign-up, no email, no password. Pick a
						model and start chatting instantly.
					</p>
					<div className="mt-10 flex flex-wrap items-center justify-center gap-2">
						<Badge variant="secondary" className="rounded-full px-3 py-1">
							No login required
						</Badge>
						<Badge variant="secondary" className="rounded-full px-3 py-1">
							500K free tokens
						</Badge>
						<Badge variant="secondary" className="rounded-full px-3 py-1">
							{FREE_MODELS.length} AI models
						</Badge>
						<Badge variant="secondary" className="rounded-full px-3 py-1">
							Open source
						</Badge>
					</div>
				</div>
			</section>

			{/* Model Table */}
			<section className="ss-home-rule">
				<div className="ss-home-head">
					<h2 className="ss-home-h2">Free AI Models Available Without Login</h2>
					<p className="ss-home-body mt-3 max-w-2xl text-sm">
						All models below work without login or sign-up. Click any model to start a free AI chat
						instantly.
					</p>
				</div>

				<section
					className="ss-home-table-scroll"
					aria-label="Free AI models available without login"
					/* biome-ignore lint/a11y/noNoninteractiveTabindex: a region that scrolls horizontally has to be focusable, or a keyboard-only visitor cannot reach the columns past the fold. The labelled landmark is what makes the focus stop meaningful. */
					tabIndex={0}
				>
					<table className="ss-home-table">
						<thead>
							<tr>
								<th scope="col">Model</th>
								<th scope="col">Provider</th>
								<th scope="col">In the app</th>
								<th scope="col">
									<span className="sr-only">Open model page</span>
								</th>
							</tr>
						</thead>
						<tbody>
							{FREE_MODELS.map((model) => (
								<tr key={model.slug}>
									<td>
										<Link className="ss-home-link" href={`/free/${model.slug}`}>
											{model.name}
										</Link>
									</td>
									<td>{model.provider}</td>
									<td>
										<span
											className="ss-home-tag"
											data-tone={model.access === "offline" ? "accent" : undefined}
										>
											{ACCESS_LABEL[model.access]}
										</span>
									</td>
									<td>
										<Link className="ss-home-forward" href={`/free/${model.slug}`}>
											Run it
											<LinkSquare02Icon aria-hidden="true" className="size-3.5" />
										</Link>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</section>
			</section>

			{/* Why SurfSense */}
			<section className="ss-home-rule">
				<div className="ss-home-head">
					<h2 className="ss-home-h2">Why Use SurfSense as Your Free ChatGPT Alternative</h2>
				</div>

				<div className="ss-home-grid ss-home-grid-3">
					<div className="ss-home-cell">
						<h3 className="ss-home-h3">Multiple AI Models in One Place</h3>
						<p className="ss-home-body mt-2 text-sm">
							Access ChatGPT, Claude AI free, Gemini, DeepSeek, and more. Works like sites like
							ChatGPT but with all AI models available, not just GPT. A true free AI chatbot like
							ChatGPT and beyond.
						</p>
					</div>
					<div className="ss-home-cell">
						<h3 className="ss-home-h3">No Login, No Sign-Up Required</h3>
						<p className="ss-home-body mt-2 text-sm">
							Start using ChatGPT free online immediately. No email, no password, no verification.
							Get ChatGPT no login access and Claude AI free access from one platform. AI with no
							restrictions on which model you can use.
						</p>
					</div>
					<div className="ss-home-cell">
						<h3 className="ss-home-h3">Open Source NotebookLM Alternative</h3>
						<p className="ss-home-body mt-2 text-sm">
							SurfSense is a free, open source NotebookLM alternative with document Q&A and
							citations, integrations with Slack, Google Drive, Notion, and Confluence, plus team
							collaboration and self-hosting support.
						</p>
					</div>
				</div>
			</section>

			{/* CTA */}
			<section className="ss-home-rule ss-home-pad py-16">
				<div className="mx-auto max-w-2xl text-center">
					<h2 className="ss-home-h2">Want More Features?</h2>
					<p className="ss-home-body mt-3">
						Create a free SurfSense account to unlock $5 of premium credit, document uploads with
						citations, team collaboration, and integrations with Slack, Google Drive, Notion, and
						30+ more tools.
					</p>
					<div className="mt-8 flex justify-center">
						<HomeButton asChild size="xl">
							<Link href="/register">Create Free Account</Link>
						</HomeButton>
					</div>
				</div>
			</section>

			{/* FAQ */}
			<section className="ss-home-rule" aria-labelledby="ss-free-faq-label">
				<div className="ss-home-head">
					<h2 id="ss-free-faq-label" className="ss-home-h2">
						Frequently Asked Questions
					</h2>
				</div>

				<div className="ss-home-grid">
					{FAQ_ITEMS.map((item) => (
						<details key={item.question} className="ss-home-faq">
							<summary className="ss-home-faq-summary">
								<span className="ss-home-h3">{item.question}</span>
								<span aria-hidden="true" className="ss-home-faq-marker" />
							</summary>
							<div className="ss-home-faq-answer">
								<p className="ss-home-body">{item.answer}</p>
							</div>
						</details>
					))}
				</div>
			</section>

			{/* Internal links */}
			<nav aria-label="Related pages" className="ss-home-rule ss-home-pad py-12">
				<h2 className="ss-home-h3">Explore SurfSense</h2>
				<ul className="mt-4 flex list-none flex-wrap gap-2 p-0">
					<li>
						<HomeButton variant="outline" size="lg" asChild>
							<Link href="/pricing">Pricing</Link>
						</HomeButton>
					</li>
					<li>
						<HomeButton variant="outline" size="lg" asChild>
							<Link href="/docs">Documentation</Link>
						</HomeButton>
					</li>
					<li>
						<HomeButton variant="outline" size="lg" asChild>
							<Link href="/blog">Blog</Link>
						</HomeButton>
					</li>
					<li>
						<HomeButton variant="outline" size="lg" asChild>
							<Link href="/register">Sign Up Free</Link>
						</HomeButton>
					</li>
				</ul>
			</nav>
		</>
	);
}
