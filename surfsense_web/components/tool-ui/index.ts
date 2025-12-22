/**
 * Tool UI Components
 *
 * This module exports custom UI components for assistant tools.
 * These components are registered with assistant-ui to render
 * rich UI when specific tools are called by the agent.
 */

export { Audio } from "./audio";
export { GeneratePodcastToolUI } from "./generate-podcast";
export {
  DeepAgentThinkingToolUI,
  InlineThinkingDisplay,
  type ThinkingStep,
  type DeepAgentThinkingArgs,
  type DeepAgentThinkingResult,
} from "./deepagent-thinking";
export {
  LinkPreviewToolUI,
  MultiLinkPreviewToolUI,
  type LinkPreviewArgs,
  type LinkPreviewResult,
  type MultiLinkPreviewArgs,
  type MultiLinkPreviewResult,
} from "./link-preview";
export {
  MediaCard,
  MediaCardErrorBoundary,
  MediaCardLoading,
  MediaCardSkeleton,
  parseSerializableMediaCard,
  type MediaCardProps,
  type SerializableMediaCard,
} from "./media-card";
export {
  Image,
  ImageErrorBoundary,
  ImageLoading,
  ImageSkeleton,
  parseSerializableImage,
  type ImageProps,
  type SerializableImage,
} from "./image";
export {
  DisplayImageToolUI,
  type DisplayImageArgs,
  type DisplayImageResult,
} from "./display-image";
