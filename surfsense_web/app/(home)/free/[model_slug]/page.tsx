import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { HomeButton } from "@/components/homepage/home/home-button";
import { BreadcrumbNav } from "@/components/seo/breadcrumb-nav";
import { FAQJsonLd, JsonLd } from "@/components/seo/json-ld";
import { DOWNLOADS_URL } from "@/components/site/site-content";
import { Badge } from "@/components/ui/badge";
import { FlowButton } from "@/components/ui/flow-button";
import { CheckIcon } from "@/components/ui/icons";
import { FREE_MODELS, type FreeModel, freeModelLabel, isPublishedSlug } from "@/lib/free-models";

/**
 * `/free/<model>` — the page the closed hosted chat left behind.
 *
 * This route used to mount the anonymous chat client over a block of SEO copy.
 * The hosted free chat is switched off, so the page's job is now the one thing
 * worth doing with the traffic it still gets: tell the visitor what happened
 * and hand them the desktop app, which is the free version from here on.
 *
 * Two constraints shape it:
 *
 * - **It answers for any slug this site could have published.** The URLs Google
 *   holds are the old service's own model slugs (`gpt-5.4-mini-no-login` and
 *   friends), and those are the pages with the traffic. `freeModelLabel` names
 *   them whether or not they are catalog rows, because 404ing them would throw
 *   away exactly the visitors this page exists to convert. A slug outside that
 *   shape is a different matter: it is not a URL anyone can be arriving from,
 *   and both the label and the canonical URL below end up inside a JSON-LD
 *   `<script>` block, so it is turned away rather than echoed.
 * - **Every claim is true of the shipped app.** The old copy on this route
 *   promised free hosted inference and a 500,000-token allowance, which is now
 *   false, so none of it survived. What replaced it says only what the desktop
 *   app does: no account, your own key or a local model, files on your disk.
 *
 * Rendered in the site design via the `/free/` prefix in `SITE_DESIGN_PREFIXES`
 * (`components/site/site-shell.tsx`). A server component, no client JavaScript
 * beyond the hero button.
 */

interface PageProps {
	params: Promise<{ model_slug: string }>;
}

/** Catalog rows carry a provider and a local/BYO-key answer; an old hosted slug
 *  carries neither, so the page falls back to the generic wording. */
function findModel(slug: string): FreeModel | undefined {
	return FREE_MODELS.find((model) => model.slug === slug);
}

/** Short, checkable claims about the app, beside the statement half of a split
 *  section — the same idiom `/private-ai-for-business` uses. */
const APP_PROOF: string[] = [
	"No account, no login, no seat",
	"No token allowance to run out",
	"Your own key, billed at cost by your provider",
	"Or a local model, with no key at all",
	"Sources and chats stay in a folder on your disk",
	"Free, and the source is public",
];

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
	const { model_slug } = await params;
	if (!isPublishedSlug(model_slug)) {
		return { title: "Page not found | SurfSense", robots: { index: false, follow: false } };
	}

	const label = freeModelLabel(model_slug);
	const lower = label.toLowerCase();
	const canonicalUrl = `https://www.surfsense.com/free/${model_slug}`;

	const title = `${label} Free, No Login: Now a Free Desktop App | SurfSense`;
	const description = `Our hosted ${label} chat is closed. ${label} now runs in the free SurfSense desktop app on your own machine, with no account, no login and no token cap. Windows, macOS and Linux.`;

	return {
		title,
		description,
		alternates: { canonical: canonicalUrl },
		// The per-model pattern the closed service ranked on, kept as-is: these
		// are the queries still arriving at this URL.
		keywords: [
			`${lower} free`,
			`free ${lower}`,
			`${lower} online`,
			`${lower} online free`,
			`${lower} without login`,
			`${lower} no login`,
			`${lower} no sign up`,
			`${lower} free without login`,
			`${lower} free no login`,
			`${lower} chat free`,
			`${lower} free online`,
			`use ${lower} for free`,
			`use ${lower} without login`,
			`run ${lower} locally`,
			`${lower} offline`,
			`${lower} alternative free`,
			"free ai chat no login",
			"ai chat no login",
			"free local ai app",
			"private ai for business",
			"notebooklm alternative",
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
					alt: `${label} in the free SurfSense desktop app`,
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

/** The catalog rows prerender. Anything else — every slug the closed service
 *  published — is rendered on demand, which is the default for this route. */
export function generateStaticParams() {
	return FREE_MODELS.map((model) => ({ model_slug: model.slug }));
}

export default async function FreeModelPage({ params }: PageProps) {
	const { model_slug } = await params;
	if (!isPublishedSlug(model_slug)) {
		notFound();
	}

	const label = freeModelLabel(model_slug);
	const model = findModel(model_slug);
	const runsOffline = model?.access === "offline";
	const provider = model?.provider;

	const faqItems = [
		{
			question: `Can I still use ${label} without login?`,
			answer: `Not on our servers: the hosted free chat that used to run on this page is closed. The SurfSense desktop app has no account and no login at all, so nothing there asks you to sign in. ${
				runsOffline
					? `${label} is in the app's local model catalog, so it downloads and runs on your own hardware.`
					: `For ${label} you supply your own API key, or run one of the app's local models with no key.`
			}`,
		},
		{
			question: "Is the SurfSense desktop app free?",
			answer:
				"Yes. The app and every update are free forever on Windows, macOS and Linux, and a 30-day licence for the scraper plugins comes with it. There is no account to create and no trial clock on the app itself.",
		},
		{
			question: "What happened to the 500,000 free tokens?",
			answer:
				"They were a shared allowance on our hosted service, and that service is switched off. The app has no allowance because we are not paying for the inference any more: you either point it at your own provider key, which your provider bills you for at cost, or run a model on your own hardware for nothing.",
		},
		{
			question: `Do I need an API key to run ${label}?`,
			answer: runsOffline
				? `No. ${label} is one of the models the app downloads into its own local catalog, so it runs on your machine with no key and no network connection. You can still add a key for a hosted model later if you want one.`
				: `For ${label} itself, yes: the app connects to any OpenAI-compatible endpoint, so you paste the base URL${
						provider ? ` for ${provider}` : ""
					} and your own key. If you would rather not have a key at all, the app ships a local catalog that runs a Qwen3 model offline for free.`,
		},
		{
			question: "Where does my data go now?",
			answer:
				"Nowhere. Sources, chats and everything generated from them live in one local workspace, a folder in your user directory with a database file in it. We hold no copy and keep no log, and with no account there is nothing tying you to one. Anonymous chat was never stored in a database either, so there is nothing of yours left on the old service.",
		},
	];

	return (
		<>
			{/* The app is the product being described now, and it really is free on
			    all three platforms, so this is the claim the page carries. The old
			    WebApplication block advertised a free hosted chat offer, which no
			    longer exists. */}
			<JsonLd
				data={{
					"@context": "https://schema.org",
					"@type": "SoftwareApplication",
					name: "SurfSense",
					description: `A private AI workspace that runs on your own machine. Use ${label} with your own key, or run a local model with no key at all.`,
					url: `https://www.surfsense.com/free/${model_slug}`,
					applicationCategory: "BusinessApplication",
					operatingSystem: "Windows, macOS, Linux",
					downloadUrl: "https://www.surfsense.com/downloads",
					offers: {
						"@type": "Offer",
						price: 0,
						priceCurrency: "USD",
						description:
							"The full app and every update on Windows, macOS and Linux, forever, with no account.",
					},
					publisher: {
						"@type": "Organization",
						name: "SurfSense",
						url: "https://www.surfsense.com",
					},
				}}
			/>
			<FAQJsonLd questions={faqItems} />

			<section className="ss-home-hero ss-home-pad">
				<div className="mx-auto max-w-3xl text-center">
					<div className="flex justify-center">
						<BreadcrumbNav
							className="ss-home-breadcrumb justify-center"
							items={[
								{ name: "Free AI models", href: "/free" },
								{ name: label, href: `/free/${model_slug}` },
							]}
						/>
					</div>

					<Badge variant="secondary" className="mt-6 rounded-full px-3 py-1">
						Hosted chat closed
					</Badge>

					<h1 className="ss-home-display mt-4">
						{label} free chat has moved to{" "}
						<span className="ss-home-accent">a free desktop app</span>
					</h1>

					<p className="ss-home-lede mx-auto mt-8 max-w-2xl">
						The hosted chat that used to run on this page is switched off. Everything it did now
						runs on your own machine instead: still no account, still no login, and no token
						allowance to run out of.
					</p>

					<div className="mt-10 flex justify-center">
						<FlowButton href={DOWNLOADS_URL} text="Download for desktop" />
					</div>

					<p className="ss-home-body mx-auto mt-6 max-w-xl text-sm">
						Windows, macOS and Linux. Free forever, and{" "}
						<Link className="ss-home-link" href="/pricing">
							the source is public
						</Link>
						.
					</p>
				</div>
			</section>

			<section className="ss-home-rule">
				<div className="ss-home-head">
					<p className="ss-home-eyebrow">What changed</p>
					<h2 className="ss-home-h2 mt-2">
						We stopped running a hosted free tier, not the free version
					</h2>
				</div>

				<div className="ss-home-pad py-12">
					<div className="ss-home-body flex max-w-3xl flex-col gap-4">
						<p>
							The anonymous chat on this page ran on our servers against a shared token pool. That
							is the part that is gone. SurfSense itself is not going anywhere: it is a desktop app
							now, and the app is the free version.
						</p>
						<p>
							That swap is why there is no allowance any more. We are not paying for your inference,
							so there is nothing to meter: you bring a key and your provider bills you at cost, or
							you run a model on your own hardware and pay nobody. Either way the cap that used to
							cut you off does not exist.
						</p>
					</div>
				</div>
			</section>

			<section className="ss-home-rule">
				<div className="ss-home-head">
					<p className="ss-home-eyebrow">In the app</p>
					<h2 className="ss-home-h2 mt-2">How to run {label} on your own machine</h2>
				</div>

				<div className="ss-home-grid ss-home-grid-3">
					<div className="ss-home-cell">
						<h3 className="ss-home-h3">
							{runsOffline ? "Download it and go" : "Bring your own key"}
						</h3>
						<p className="ss-home-body mt-2 text-sm">
							{runsOffline
								? `${label} is in the app's own model catalog. Pick it, let the app download it, and it runs on your hardware from then on, with no key and no network connection.`
								: `The app connects to any OpenAI-compatible endpoint. Paste the base URL${
										provider ? ` for ${provider}` : ""
									} and your own key, pick ${label}, and it runs from your machine against your own account.`}
						</p>
					</div>
					<div className="ss-home-cell">
						<h3 className="ss-home-h3">
							{runsOffline ? "Or add a hosted model" : "Or skip the key entirely"}
						</h3>
						<p className="ss-home-body mt-2 text-sm">
							{runsOffline
								? "If you want a frontier model for the hard questions, add an OpenAI-compatible connection with your own key and switch between the two per chat."
								: "The app ships a local catalog it downloads through Ollama, so a Qwen3 model runs on your own hardware for nothing. No key, no account, and it works with the network unplugged."}
						</p>
					</div>
					<div className="ss-home-cell">
						<h3 className="ss-home-h3">It is a workspace, not a chat box</h3>
						<p className="ss-home-body mt-2 text-sm">
							Add PDFs, Word files, spreadsheets and pages, ask across all of them with citations,
							and turn the answers into a deck, a report or a briefing podcast.
						</p>
					</div>
				</div>
			</section>

			<section className="ss-home-rule ss-home-split">
				<div className="ss-home-statement">
					<h2 className="ss-home-h2">Free, and this time without the asterisk</h2>
					<div className="ss-home-body mt-5 flex flex-col gap-4">
						<p>
							The hosted chat was free until the shared pool ran out, which is the part nobody
							liked. The app has no pool to share: it runs on your machine, so the only limits are
							your own hardware and whatever your provider charges you.
						</p>
						<p>
							There is no seat to provision, no tenant to configure and no admin console, because
							there is no server. The only identity involved is your operating system user.
						</p>
					</div>
					<p className="mt-6">
						<Link className="ss-home-forward" href="/pricing">
							What a licence adds
						</Link>
					</p>
				</div>

				<ul className="ss-home-grid m-0 list-none p-0">
					{APP_PROOF.map((point) => (
						<li key={point} className="flex items-center gap-3 px-(--home-gutter) py-3.5">
							<CheckIcon aria-hidden="true" className="size-3.5 shrink-0 text-(--home-accent)" />
							<span className="ss-home-body text-sm">{point}</span>
						</li>
					))}
				</ul>
			</section>

			<section className="ss-home-rule" aria-labelledby="ss-free-model-faq">
				<div className="ss-home-head">
					<h2 id="ss-free-model-faq" className="ss-home-h2">
						{label} without login: frequently asked questions
					</h2>
				</div>

				<div className="ss-home-grid">
					{faqItems.map((item) => (
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

			<section className="ss-home-rule ss-home-pad py-16">
				<div className="mx-auto max-w-2xl text-center">
					<h2 className="ss-home-h2">Get the app and run {label} locally</h2>
					<p className="ss-home-body mt-3">
						One installer, no account, and your documents never leave the machine you put them on.
					</p>
					<div className="mt-8 flex flex-wrap items-center justify-center gap-3">
						<HomeButton asChild size="xl">
							<Link href={DOWNLOADS_URL}>Download SurfSense</Link>
						</HomeButton>
						<HomeButton asChild variant="outline" size="xl">
							<Link href="/free">All AI models</Link>
						</HomeButton>
					</div>
				</div>
			</section>

			<nav aria-label="Other AI models" className="ss-home-rule ss-home-pad py-12">
				<h2 className="ss-home-h3">Other models you can run locally</h2>
				<ul className="mt-4 flex list-none flex-wrap gap-2 p-0">
					{FREE_MODELS.filter((other) => other.slug !== model_slug)
						.slice(0, 6)
						.map((other) => (
							<li key={other.slug}>
								<HomeButton variant="outline" size="lg" asChild>
									<Link href={`/free/${other.slug}`}>{other.name}</Link>
								</HomeButton>
							</li>
						))}
					<li>
						<HomeButton variant="outline" size="lg" asChild>
							<Link href="/free">View all models</Link>
						</HomeButton>
					</li>
				</ul>
			</nav>
		</>
	);
}
