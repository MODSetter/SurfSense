import { SquareArrowOutUpRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FreeChatPage } from "@/components/free-chat/free-chat-page";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { AnonModel } from "@/contracts/types/anonymous-chat.types";
import { BACKEND_URL } from "@/lib/env-config";

interface PageProps {
	params: Promise<{ model_slug: string }>;
}

async function getModel(slug: string): Promise<AnonModel | null> {
	try {
		const res = await fetch(
			`${BACKEND_URL}/api/v1/public/anon-chat/models/${encodeURIComponent(slug)}`,
			{ next: { revalidate: 300 } }
		);
		if (!res.ok) return null;
		return res.json();
	} catch {
		return null;
	}
}

async function getAllModels(): Promise<AnonModel[]> {
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

function buildSeoTitle(model: AnonModel): string {
	if (model.seo_title) return model.seo_title;
	return `Chat with ${model.name} Free, No Login | SurfSense`;
}

function buildSeoDescription(model: AnonModel): string {
	if (model.seo_description) return model.seo_description;
	return `Use ${model.name} free online without login. No sign-up required. Chat with ${model.name} by ${model.provider} instantly on SurfSense, the open source ChatGPT alternative with no login.`;
}

function buildModelFaq(model: AnonModel) {
	return [
		{
			question: `Can I use ${model.name} without login?`,
			answer: `Yes. ${model.name} is available on SurfSense without login. No account creation, no email, no password. Just open the page and start chatting with ${model.name} for free.`,
		},
		{
			question: `Is ${model.name} really free on SurfSense?`,
			answer: `Yes! You can use ${model.name} completely free without login or sign-up. SurfSense gives you 500,000 free tokens to use across any model, including ${model.name}.`,
		},
		{
			question: `How do I use ${model.name} with no login?`,
			answer: `Just start typing in the chat box above. ${model.name} will respond instantly. No login wall, no sign-up form, no verification. Your conversations are not stored in any database.`,
		},
		{
			question: `What can I do with ${model.name} on SurfSense?`,
			answer: `You can ask questions, get explanations, write content, brainstorm ideas, debug code, and more. ${model.name} is a powerful AI assistant available for free without login on SurfSense.`,
		},
		{
			question: `How is SurfSense different from using ${model.name} directly?`,
			answer: `SurfSense gives you free access without login to ${model.name} and many other AI models in one place. Create a free account to unlock document Q&A, team collaboration, and integrations with Slack, Google Drive, Notion, and more.`,
		},
	];
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
	const { model_slug } = await params;
	const model = await getModel(model_slug);
	if (!model) return { title: "Model Not Found | SurfSense" };

	const title = buildSeoTitle(model);
	const description = buildSeoDescription(model);
	const canonicalUrl = `https://surfsense.com/free/${model.seo_slug}`;
	const modelNameLower = model.name.toLowerCase();

	return {
		title,
		description,
		alternates: { canonical: canonicalUrl },
		keywords: [
			`${modelNameLower} free`,
			`free ${modelNameLower}`,
			`${modelNameLower} online`,
			`${modelNameLower} online free`,
			`${modelNameLower} without login`,
			`${modelNameLower} no login`,
			`${modelNameLower} no sign up`,
			`${modelNameLower} login free`,
			`${modelNameLower} free without login`,
			`${modelNameLower} free no login`,
			`${modelNameLower} chat free`,
			`${modelNameLower} free online`,
			`use ${modelNameLower} for free`,
			`use ${modelNameLower} without login`,
			`${modelNameLower} alternative`,
			`${modelNameLower} alternative free`,
			"chatgpt no login",
			"chatgpt without login",
			"free ai chat no login",
			"ai chat without login",
			"free ai apps",
		],
		openGraph: {
			title,
			description,
			url: canonicalUrl,
			siteName: "SurfSense",
			type: "website",
			images: [
				{
					url: "/og-image.png",
					width: 1200,
					height: 630,
					alt: `${model.name} Free Chat on SurfSense`,
				},
			],
		},
		twitter: {
			card: "summary_large_image",
			title,
			description,
			images: ["/og-image.png"],
		},
	};
}

export async function generateStaticParams() {
	const models = await getAllModels();
	return models.filter((m) => m.seo_slug).map((m) => ({ model_slug: m.seo_slug! }));
}

export default async function FreeModelPage({ params }: PageProps) {
	const { model_slug } = await params;
	const [model, allModels] = await Promise.all([getModel(model_slug), getAllModels()]);
	if (!model) notFound();

	const description = buildSeoDescription(model);
	const faqItems = buildModelFaq(model);

	const relatedModels = allModels
		.filter((m) => m.seo_slug && m.seo_slug !== model.seo_slug)
		.slice(0, 4);

	return (
		<>
			{/* Invisible SEO metadata */}
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "WebApplication",
					name: `${model.name} Free Chat Without Login - SurfSense`,
					description,
					url: `https://surfsense.com/free/${model.seo_slug}`,
					applicationCategory: "ChatApplication",
					operatingSystem: "Web",
					offers: {
						"@type": "Offer",
						price: "0",
						priceCurrency: "USD",
						description: `Free access to ${model.name} AI chat without login`,
					},
					provider: {
						"@type": "Organization",
						name: "SurfSense",
						url: "https://surfsense.com",
					},
					isPartOf: {
						"@type": "WebSite",
						name: "SurfSense",
						url: "https://surfsense.com",
					},
				}}
			/>
			<FAQJsonLd questions={faqItems} />

			{/* Chat fills the entire viewport area inside LayoutShell */}
			<div className="h-full">
				<FreeChatPage />
			</div>

			{/* SEO content: in DOM for crawlers, clipped by parent overflow-hidden */}
			<div className="border-t bg-background">
				<article className="container mx-auto px-4 py-10 max-w-3xl">
					<BreadcrumbNav
						items={[
							{ name: "Home", href: "/" },
							{ name: "Free AI Chat", href: "/free" },
							{ name: model.name, href: `/free/${model.seo_slug}` },
						]}
					/>

					<header className="mt-6 mb-6">
						<h1 className="text-2xl font-bold mb-2">Chat with {model.name} Free, No Login</h1>
						<p className="text-sm text-muted-foreground leading-relaxed">
							Use <strong>{model.name}</strong> free online without login or sign-up. No account, no
							email, no password needed. Powered by SurfSense.
						</p>
					</header>

					<Separator className="my-8" />

					<section>
						<h2 className="text-xl font-bold mb-4">
							{model.name} Free: Frequently Asked Questions
						</h2>
						<dl className="flex flex-col gap-3">
							{faqItems.map((item) => (
								<div key={item.question} className="rounded-lg border bg-card p-4">
									<dt className="font-medium text-sm">{item.question}</dt>
									<dd className="mt-1.5 text-sm text-muted-foreground leading-relaxed">
										{item.answer}
									</dd>
								</div>
							))}
						</dl>
					</section>

					{relatedModels.length > 0 && (
						<>
							<Separator className="my-8" />
							<nav aria-label="Other free AI models">
								<h2 className="text-xl font-bold mb-4">Try Other Free AI Models</h2>
								<div className="flex flex-wrap gap-2">
									{relatedModels.map((m) => (
										<Button key={m.id} variant="outline" size="sm" asChild>
											<Link href={`/free/${m.seo_slug}`}>
												{m.name}
												<SquareArrowOutUpRight className="size-3" />
											</Link>
										</Button>
									))}
									<Button variant="outline" size="sm" asChild>
										<Link href="/free">View All Models</Link>
									</Button>
								</div>
							</nav>
						</>
					)}
				</article>
			</div>
		</>
	);
}
