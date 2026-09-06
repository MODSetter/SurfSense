import { SquareArrowOutUpRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { RetiredChatNotice } from "@/components/free-chat/retired-chat-notice";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { AnonModel } from "@/contracts/types/anonymous-chat.types";
import { SERVER_BACKEND_URL } from "@/lib/env-config";

interface PageProps {
	params: Promise<{ model_slug: string }>;
}

async function getModel(slug: string): Promise<AnonModel | null> {
	try {
		const res = await fetch(
			`${SERVER_BACKEND_URL}/api/v1/public/anon-chat/models/${encodeURIComponent(slug)}`,
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
		const res = await fetch(`${SERVER_BACKEND_URL}/api/v1/public/anon-chat/models`, {
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
	return `Chat with ${model.name} Free Online | SurfSense`;
}

function buildSeoDescription(model: AnonModel): string {
	if (model.seo_description) return model.seo_description;
	return `Use ${model.name} free online with a SurfSense account. Chat with ${model.name} by ${model.provider}, bring your own documents, and switch models any time on SurfSense, the open source ChatGPT alternative.`;
}

/**
 * These answers are mirrored into FAQ structured data, so they have to match
 * what the page actually does. They previously promised no login, no sign-up
 * form, and 500,000 anonymous tokens — all untrue since anonymous chat was
 * retired, and an accuracy violation Google can pull the rich result over.
 */
function buildModelFaq(model: AnonModel) {
	return [
		{
			question: `Can I use ${model.name} for free?`,
			answer: `Yes. ${model.name} is available on SurfSense with a free account. Signing up takes a moment and includes a monthly allowance you can spend on ${model.name} or any other model we support.`,
		},
		{
			question: `Do I need an account to use ${model.name}?`,
			answer: `Yes. SurfSense used to offer ${model.name} without an account, but that has been retired. A free account keeps your chat history, lets you upload your own documents, and works across every model.`,
		},
		{
			question: `How do I start using ${model.name}?`,
			answer: `Create a free SurfSense account, then pick ${model.name} from the model selector and start typing. You can switch models mid-conversation without losing your thread.`,
		},
		{
			question: `What can I do with ${model.name} on SurfSense?`,
			answer: `You can ask questions, get explanations, write content, brainstorm ideas, debug code, and query your own documents. ${model.name} is one of many models available on SurfSense.`,
		},
		{
			question: `How is SurfSense different from using ${model.name} directly?`,
			answer: `SurfSense puts ${model.name} and many other AI models in one place, on top of your own knowledge base. It adds document Q&A, team collaboration, and integrations with Slack, Google Drive, Notion, and more.`,
		},
	];
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
	const { model_slug } = await params;
	const model = await getModel(model_slug);
	if (!model) return { title: "Model Not Found | SurfSense" };

	const title = buildSeoTitle(model);
	const description = buildSeoDescription(model);
	const canonicalUrl = `https://www.surfsense.com/free/${model.seo_slug}`;
	const modelNameLower = model.name.toLowerCase();

	return {
		title,
		description,
		alternates: { canonical: canonicalUrl },
		// The "no login" variants are gone with the product they described.
		// Keeping them would win clicks onto a page that cannot deliver what
		// the query asked for, which costs more in bounce rate than it gains.
		keywords: [
			`${modelNameLower} free`,
			`free ${modelNameLower}`,
			`${modelNameLower} online`,
			`${modelNameLower} online free`,
			`${modelNameLower} chat free`,
			`${modelNameLower} free online`,
			`use ${modelNameLower} for free`,
			`${modelNameLower} alternative`,
			`${modelNameLower} alternative free`,
			"free ai chat",
			"chatgpt alternative",
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
	return models.flatMap((m) => (m.seo_slug ? [{ model_slug: m.seo_slug }] : []));
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
					name: `${model.name} Free Chat - SurfSense`,
					description,
					url: `https://www.surfsense.com/free/${model.seo_slug}`,
					applicationCategory: "ChatApplication",
					operatingSystem: "Web",
					offers: {
						"@type": "Offer",
						price: "0",
						priceCurrency: "USD",
						description: `Free ${model.name} access with a SurfSense account`,
					},
					provider: {
						"@type": "Organization",
						name: "SurfSense",
						url: "https://www.surfsense.com",
					},
					isPartOf: {
						"@type": "WebSite",
						name: "SurfSense",
						url: "https://www.surfsense.com",
					},
				}}
			/>
			<FAQJsonLd questions={faqItems} />

			{/* Anonymous chat is retired; the page and its rankings are not. */}
			<div>
				<RetiredChatNotice modelName={model.name} />

				<div className="border-t bg-background">
					<article className="container mx-auto px-4 py-10 max-w-3xl">
						<header className="mb-6">
							<h1 className="text-2xl font-bold mb-2">Chat with {model.name} on SurfSense</h1>
							<p className="text-sm text-muted-foreground leading-relaxed">
								Use <strong>{model.name}</strong> online with a free SurfSense account, alongside
								every other model we support, your own documents, and your connected tools.
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
			</div>
		</>
	);
}
