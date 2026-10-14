import { HomeBadge } from "@/components/homepage/home/home-badge";
import { FORMATS, type Format } from "@/components/homepage/home/home-content";
import { FormatCard } from "@/components/homepage/home/home-formats/format-card";
import { FlashcardsPreview } from "@/components/homepage/home/home-formats/previews/flashcards-preview";
import { ImagePreview } from "@/components/homepage/home/home-formats/previews/image-preview";
import { InfographicPreview } from "@/components/homepage/home/home-formats/previews/infographic-preview";
import { MindMapPreview } from "@/components/homepage/home/home-formats/previews/mind-map-preview";
import { PodcastPreview } from "@/components/homepage/home/home-formats/previews/podcast-preview";
import { QuizPreview } from "@/components/homepage/home/home-formats/previews/quiz-preview";
import { SlidesPreview } from "@/components/homepage/home/home-formats/previews/slides-preview";
import { ReadExportCard } from "@/components/homepage/home/home-formats/read-export-card";
import { sectionSpacing } from "@/components/homepage/home/home-section-spacing";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/lib/utils";

const BY_KEY = new Map(FORMATS.map((format) => [format.key, format]));

function format(key: string): Format {
	const found = BY_KEY.get(key);
	if (!found) throw new Error(`Unknown artifact format: ${key}`);
	return found;
}

const WRITTEN = ["summary", "docx", "pdf", "html", "xlsx"].map(format);

/**
 * The twelve Studio formats as a bento of miniatures, in four groups so they
 * read as four ideas: listen, present, study, read and export. The headline
 * formats get the large, sky-washed cards.
 *
 * Not one of the brief's eight H2s, so the headline is a `<p>` styled as one.
 */
export function HomeFormats() {
	return (
		<section className={sectionSpacing.foot}>
			<div className={cn("text-center", sectionSpacing.head)}>
				<HomeBadge>Artifacts</HomeBadge>
				<p className={cn(siteText.h2, "mt-4")}>Twelve things one set of sources can become</p>
			</div>

			<div className="mt-10 grid gap-4 md:grid-cols-2 lg:mt-14 lg:grid-cols-4">
				<FormatCard
					format={format("podcast")}
					group="Listen"
					preview={<PodcastPreview />}
					wash
					className="md:col-span-2 lg:row-span-2"
				/>
				<FormatCard
					format={format("pptx")}
					group="Present"
					preview={<SlidesPreview />}
					wash
					className="md:col-span-2"
				/>
				<FormatCard
					format={format("infographic")}
					group="Present"
					preview={<InfographicPreview />}
				/>
				<FormatCard format={format("image")} group="Present" preview={<ImagePreview />} />
				<FormatCard
					format={format("mindmap")}
					group="Study"
					preview={<MindMapPreview />}
					wash
					className="md:col-span-2"
				/>
				<FormatCard format={format("flashcards")} group="Study" preview={<FlashcardsPreview />} />
				<FormatCard format={format("quiz")} group="Study" preview={<QuizPreview />} />
				<ReadExportCard formats={WRITTEN} className="md:col-span-2 lg:col-span-4" />
			</div>
		</section>
	);
}
