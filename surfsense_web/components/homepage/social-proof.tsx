"use client";

import {
	IconBrandLinkedin,
	IconBrandTiktok,
	IconBrandX,
	IconBrandYoutube,
} from "@tabler/icons-react";
import { Component, type ReactNode, useEffect, useRef, useState } from "react";
import { LinkedInEmbed, TikTokEmbed, XEmbed, YouTubeEmbed } from "react-social-media-embed";
import { Reveal } from "@/components/connectors-marketing/reveal";

type Post =
	| { kind: "youtube"; url: string; title: string; channel: string }
	| { kind: "x"; url: string }
	| { kind: "linkedin"; url: string; postUrl: string }
	| { kind: "tiktok"; url: string };

/**
 * Organic SurfSense coverage — real posts embedded live with react-social-media-embed,
 * grouped into three platform-uniform marquee rows (heights match within a row).
 *
 * Note: LinkedIn only renders when the author enabled embedding on the post; if
 * disabled, the EmbedBoundary swaps in a link card to the original.
 *
 * ponytail: three rows, each list duplicated once for a seamless CSS loop. Ceiling:
 * heavy third-party embeds. Mitigated by lazy-mounting the whole section on scroll
 * (IntersectionObserver). Upgrade path: per-card virtualization, or swap YouTube
 * players for thumbnail links.
 */
const YOUTUBE: Post[] = [
	{
		kind: "youtube",
		url: "https://www.youtube.com/watch?v=i9AJ7PHGSGg",
		title: "SurfSense vs NotebookLM",
		channel: "rezasaad plus",
	},
	{
		kind: "youtube",
		url: "https://www.youtube.com/watch?v=VBOwuD6xVK0",
		title: "NotebookLM Is Great… Until You See SurfSense",
		channel: "Thomas AI",
	},
	{
		kind: "youtube",
		url: "https://www.youtube.com/watch?v=UaekqjhUiJM",
		title: "NotebookLM vs SurfSense en 6 pruebas reales (sorprendente)",
		channel: "NextGen IA Hub",
	},
	{
		kind: "youtube",
		url: "https://www.youtube.com/watch?v=QGjKpZJJ9aw",
		title: "Gana DINERO configurando “Cerebros de IA” privados con SurfSense",
		channel: "Creando Con La IA",
	},
	{
		kind: "youtube",
		url: "https://www.youtube.com/watch?v=cfNAIQtNbKY",
		title: "¿Adiós NotebookLM? Probé SurfSense y es BRUTAL (IA Gratis)",
		channel: "NextGen IA Hub",
	},
	{
		kind: "youtube",
		url: "https://www.youtube.com/watch?v=pIWOKSHhf38",
		title: "¿Superaron a NotebookLM? SurfSense es Open Source, privada y GRATIS",
		channel: "academIArtificial",
	},
	{
		kind: "youtube",
		url: "https://www.youtube.com/watch?v=K5xx-J_mQZ8",
		title: "¿Mejor que NotebookLM? IA GRATIS con modo local",
		channel: "Migue Baena IA",
	},
	{
		kind: "youtube",
		url: "https://www.youtube.com/watch?v=AKxM3RUBFsc",
		title: "¿Nueva IA GRATIS destroza a NotebookLM de Google? (OPEN SOURCE)",
		channel: "Inteligencia Artificial Top",
	},
	{
		kind: "youtube",
		url: "https://www.youtube.com/watch?v=jCAgeaVgPDA",
		title: "¿Nueva Herramienta IA GRATIS Destroza a NotebookLM? (OPEN SOURCE)",
		channel: "Joaquín Barberá",
	},
];

const TWEETS: Post[] = [
	{ kind: "x", url: "https://x.com/LangChain/status/1853133037019562434" },
	{ kind: "x", url: "https://x.com/MoureDev/status/1976279289780740448" },
	{ kind: "x", url: "https://x.com/GithubProjects/status/2004892541590929490" },
	{ kind: "x", url: "https://x.com/GitHub_Daily/status/1920418408736436438" },
	{ kind: "x", url: "https://x.com/tom_doerr/status/2066062170173977088" },
	{ kind: "x", url: "https://x.com/itsharmanjot/status/2066118517905354816" },
	{ kind: "x", url: "https://x.com/JulianGoldieSEO/status/2011085275133604095" },
	{ kind: "x", url: "https://x.com/L_go_mrk/status/2066482853232115847" },
	{ kind: "x", url: "https://x.com/semihdev/status/2006275500952736028" },
	{ kind: "x", url: "https://x.com/shao__meng/status/1919912860957999494" },
	{ kind: "x", url: "https://x.com/LangChain/status/1840406184316342561" },
];

const SOCIAL: Post[] = [
	{
		kind: "linkedin",
		url: "https://www.linkedin.com/embed/feed/update/urn:li:ugcPost:7448203908834938881",
		postUrl:
			"https://www.linkedin.com/posts/vikas-singh-546643206_most-ai-tools-live-in-your-browser-and-ugcPost-7448203908834938881-gR6y",
	},
	{
		kind: "linkedin",
		url: "https://www.linkedin.com/embed/feed/update/urn:li:share:7448351685409701889",
		postUrl:
			"https://www.linkedin.com/posts/neha-jain-279b80118_ive-been-using-a-lot-of-ai-tools-daily-share-7448351685409701889-JvFP",
	},
	{
		kind: "tiktok",
		url: "https://www.tiktok.com/@alejavirivera/video/7603064928114625814",
	},
];

const CARD = "mr-4 shrink-0 overflow-hidden rounded-xl border bg-card";

const SIZE: Record<Post["kind"], string> = {
	youtube: "h-[262px] w-[340px]",
	x: "h-[440px] w-[340px]",
	linkedin: "h-[540px] w-[340px]",
	tiktok: "h-[540px] w-[340px]",
};

const META: Record<Post["kind"], { Icon: typeof IconBrandX; label: string }> = {
	youtube: { Icon: IconBrandYoutube, label: "YouTube" },
	x: { Icon: IconBrandX, label: "X" },
	linkedin: { Icon: IconBrandLinkedin, label: "LinkedIn" },
	tiktok: { Icon: IconBrandTiktok, label: "TikTok" },
};

/**
 * Some embeds (notably Facebook, and LinkedIn when the author disabled embedding)
 * throw at render/mount instead of degrading gracefully. This boundary stops one
 * bad embed from taking down the whole marquee — it swaps in a link card instead.
 */
class EmbedBoundary extends Component<
	{ fallback: ReactNode; children: ReactNode },
	{ failed: boolean }
> {
	state = { failed: false };
	static getDerivedStateFromError() {
		return { failed: true };
	}
	render() {
		return this.state.failed ? this.props.fallback : this.props.children;
	}
}

function FallbackCard({ post }: { post: Post }) {
	const { Icon, label } = META[post.kind];
	const href = post.kind === "linkedin" ? post.postUrl : post.url;
	return (
		<div className={`${CARD} ${SIZE[post.kind]}`}>
			<a
				href={href}
				target="_blank"
				rel="noopener noreferrer"
				className="flex h-full w-full flex-col items-center justify-center gap-3 p-6 text-center text-sm font-medium text-muted-foreground transition-colors hover:text-brand"
			>
				<Icon className="size-8" aria-hidden />
				<span>View this post on {label}</span>
			</a>
		</div>
	);
}

function Card({ post }: { post: Post }) {
	switch (post.kind) {
		case "youtube":
			return (
				<div className={`${CARD} ${SIZE.youtube} flex flex-col`}>
					<YouTubeEmbed url={post.url} width={340} height={191} />
					<div className="flex flex-1 flex-col gap-1.5 p-3">
						<div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
							<IconBrandYoutube className="size-4 shrink-0 text-red-500" aria-hidden />
							<span className="truncate">{post.channel}</span>
						</div>
						<a
							href={post.url}
							target="_blank"
							rel="noopener noreferrer"
							className="line-clamp-2 text-sm font-medium leading-snug hover:text-brand"
						>
							{post.title}
						</a>
					</div>
				</div>
			);
		case "x":
			return (
				<div className={`${CARD} ${SIZE.x}`}>
					<XEmbed url={post.url} width={340} />
				</div>
			);
		case "linkedin":
			return (
				<div className={`${CARD} ${SIZE.linkedin}`}>
					<LinkedInEmbed url={post.url} postUrl={post.postUrl} width={340} height={540} />
				</div>
			);
		case "tiktok":
			return (
				<div className={`${CARD} ${SIZE.tiktok}`}>
					<TikTokEmbed url={post.url} width={340} />
				</div>
			);
	}
}

function Row({
	posts,
	animation,
	duration,
}: {
	posts: Post[];
	animation: "ss-marquee-l" | "ss-marquee-r";
	duration: number;
}) {
	return (
		<div className="group flex overflow-hidden">
			{/* Track holds the list twice; the -50% shift wraps seamlessly (margins, not gap). */}
			<div
				className="flex w-max shrink-0 group-hover:paused motion-reduce:paused"
				style={{ animation: `${animation} ${duration}s linear infinite` }}
			>
				{[...posts, ...posts].map((post, i) => (
					<EmbedBoundary
						key={`${post.kind}-${post.url}-${i}`}
						fallback={<FallbackCard post={post} />}
					>
						<Card post={post} />
					</EmbedBoundary>
				))}
			</div>
		</div>
	);
}

export function SocialProof() {
	// Third-party embeds are heavy; only mount them once the section scrolls near view.
	const ref = useRef<HTMLDivElement>(null);
	const [visible, setVisible] = useState(false);
	useEffect(() => {
		const el = ref.current;
		if (!el) return;
		const io = new IntersectionObserver(
			(entries) => {
				if (entries[0]?.isIntersecting) {
					setVisible(true);
					io.disconnect();
				}
			},
			{ rootMargin: "300px" }
		);
		io.observe(el);
		return () => io.disconnect();
	}, []);

	return (
		<section className="overflow-hidden py-12 sm:py-16">
			<Reveal>
				<div className="mx-auto max-w-2xl px-4 text-center">
					<h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
						Loved across the internet
					</h2>
				</div>
			</Reveal>
			<div
				ref={ref}
				className="mt-10 flex min-h-[1360px] flex-col gap-4"
				style={{
					maskImage: "linear-gradient(to right, transparent, black 6%, black 94%, transparent)",
					WebkitMaskImage:
						"linear-gradient(to right, transparent, black 6%, black 94%, transparent)",
				}}
			>
				{visible ? (
					<>
						<Row posts={YOUTUBE} animation="ss-marquee-l" duration={60} />
						<Row posts={TWEETS} animation="ss-marquee-r" duration={75} />
						{/* Only 3 social cards — pre-double so one set spans wide viewports (no loop gap). */}
						<Row posts={[...SOCIAL, ...SOCIAL]} animation="ss-marquee-l" duration={70} />
					</>
				) : null}
			</div>
			<style>{`
				@keyframes ss-marquee-l { from { transform: translateX(0); } to { transform: translateX(-50%); } }
				@keyframes ss-marquee-r { from { transform: translateX(-50%); } to { transform: translateX(0); } }
			`}</style>
		</section>
	);
}
