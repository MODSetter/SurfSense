/**
 * Public surface of the ``timeline/`` slice.
 *
 * Consumers (assistant-message, public-thread, free-chat-page, etc.)
 * import ONLY from this barrel. Internal modules — ``items/``,
 * ``tool-registry/``, ``timeline-group-row``, ``build-timeline``,
 * ``grouping``, ``subagent-rename`` — are intentionally NOT
 * re-exported. Adding consumers? Talk to the architecture doc first
 * (see §6 layering rules).
 */

export type { ThinkingStepInput } from "./build-timeline";
export { TimelineDataUI } from "./data-renderer";
export { Timeline } from "./timeline";
export type { TimelineToolComponent, TimelineToolProps } from "./tool-registry/types";
export type { ItemStatus, ReasoningItem, TimelineGroup, TimelineItem, ToolCallItem } from "./types";
