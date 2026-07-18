"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { Reveal } from "@/components/connectors-marketing/reveal";
import { MarketingSection } from "@/components/marketing/section";

/**
 * Real signups pulled from prod (Google-auth), curated to the most recognizable
 * names. These are self-serve users, not signed enterprise accounts, so the
 * heading stays honest ("Used by people at") rather than implying contracts.
 *
 * Logos live in `public/logos/` — official marks from Wikimedia Commons /
 * Wikipedia (universities use their seals). Bosta, Devoteam, and Leverage Edu
 * have no clean Wikimedia logo, so they fall back to a brand favicon. Each item
 * also falls back to a text wordmark on image error.
 */
const COMPANIES: { title: string; file: string }[] = [
	{ title: "UC Berkeley", file: "berkeley.svg" },
	{ title: "USC", file: "usc.svg" },
	{ title: "Texas A&M", file: "tamu.svg" },
	{ title: "UW–Madison", file: "wisc.svg" },
	{ title: "Pitt", file: "pitt.svg" },
	{ title: "Korean Air", file: "koreanair.svg" },
	{ title: "Iron Mountain", file: "ironmountain.svg" },
	{ title: "Globant", file: "globant.svg" },
	{ title: "Devoteam", file: "devoteam.png" },
	{ title: "VNG", file: "vng.svg" },
	{ title: "TPBank", file: "tpbank.svg" },
	{ title: "OpenGov", file: "opengov.png" },
	{ title: "WeLab", file: "welab.png" },
	{ title: "Leverage Edu", file: "leverageedu.png" },
	{ title: "Zopper", file: "zopper.png" },
	{ title: "Tec de Monterrey", file: "tec.svg" },
	{ title: "Chulalongkorn", file: "chula.svg" },
	{ title: "Univ. of Bristol", file: "bristol.svg" },
	{ title: "Nutresa", file: "nutresa.svg" },
	{ title: "Bosta", file: "bosta.png" },
];

const LOGOS_PER_SET = 10;
const TOTAL_SETS = Math.ceil(COMPANIES.length / LOGOS_PER_SET);

function LogoItem({ title, file }: { title: string; file: string }) {
	const [failed, setFailed] = useState(false);

	if (failed) {
		return (
			<span className="text-sm font-semibold text-neutral-500 dark:text-neutral-400">{title}</span>
		);
	}

	return (
		// biome-ignore lint/performance/noImgElement: swapped in/out by the cycling animation, next/image adds no value here
		<img
			src={`/logos/${file}`}
			alt={title}
			title={title}
			width={130}
			height={40}
			loading="lazy"
			onError={() => setFailed(true)}
			// dark mode: dark-on-transparent marks would vanish, so render every logo as a
			// uniform light silhouette (brightness-0 + invert) instead of relying on its own color
			className="h-10 w-auto max-w-[130px] object-contain opacity-60 grayscale transition duration-300 hover:opacity-100 hover:grayscale-0 dark:opacity-70 dark:brightness-0 dark:invert dark:hover:opacity-100"
		/>
	);
}

export function LogoCloud() {
	const [currentSet, setCurrentSet] = useState(0);

	useEffect(() => {
		const interval = setInterval(() => {
			setCurrentSet((prev) => (prev + 1) % TOTAL_SETS);
		}, 3000);
		return () => clearInterval(interval);
	}, []);

	const startIndex = currentSet * LOGOS_PER_SET;
	const currentLogos = Array.from(
		{ length: LOGOS_PER_SET },
		(_, i) => COMPANIES[(startIndex + i) % COMPANIES.length]
	);

	return (
		<MarketingSection>
			<Reveal>
				<h2 className="mx-auto max-w-xl text-center text-lg font-medium text-neutral-600 dark:text-neutral-400">
					Used by people at
				</h2>
			</Reveal>
			<div className="mx-auto mt-10 grid max-w-4xl grid-cols-3 gap-8 sm:grid-cols-5">
				<AnimatePresence mode="popLayout">
					{currentLogos.map((logo, index) => (
						<motion.div
							key={`${logo.title}-${currentSet}-${index}`}
							initial={{ x: 40, opacity: 0, filter: "blur(8px)" }}
							animate={{ x: 0, opacity: 1, filter: "blur(0px)" }}
							exit={{ x: -40, opacity: 0, filter: "blur(8px)" }}
							transition={{ duration: 0.4, ease: "easeOut", delay: index * 0.05 }}
							className="flex items-center justify-center"
						>
							<LogoItem title={logo.title} file={logo.file} />
						</motion.div>
					))}
				</AnimatePresence>
			</div>
		</MarketingSection>
	);
}
