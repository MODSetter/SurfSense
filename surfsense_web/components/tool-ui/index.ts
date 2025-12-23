/**
 * Tool UI Components
 *
 * This module exports custom UI components for assistant tools.
 * These components are registered with assistant-ui to render
 * rich UI when specific tools are called by the agent.
 */

export {
	Article,
	ArticleErrorBoundary,
	ArticleLoading,
	type ArticleProps,
	ArticleSkeleton,
	parseSerializableArticle,
	type SerializableArticle,
} from "./article";
export { Audio } from "./audio";
export {
	type DeepAgentThinkingArgs,
	type DeepAgentThinkingResult,
	DeepAgentThinkingToolUI,
	InlineThinkingDisplay,
	type ThinkingStep,
} from "./deepagent-thinking";
export {
	type DisplayImageArgs,
	type DisplayImageResult,
	DisplayImageToolUI,
} from "./display-image";
export { GeneratePodcastToolUI } from "./generate-podcast";
export {
	Image,
	ImageErrorBoundary,
	ImageLoading,
	type ImageProps,
	ImageSkeleton,
	parseSerializableImage,
	type SerializableImage,
} from "./image";
export {
	type LinkPreviewArgs,
	type LinkPreviewResult,
	LinkPreviewToolUI,
	type MultiLinkPreviewArgs,
	type MultiLinkPreviewResult,
	MultiLinkPreviewToolUI,
} from "./link-preview";
export {
	MediaCard,
	MediaCardErrorBoundary,
	MediaCardLoading,
	type MediaCardProps,
	MediaCardSkeleton,
	parseSerializableMediaCard,
	type SerializableMediaCard,
} from "./media-card";
export {
	type ScrapeWebpageArgs,
	type ScrapeWebpageResult,
	ScrapeWebpageToolUI,
} from "./scrape-webpage";
