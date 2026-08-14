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

export { TimelineDataUI } from "./data-renderer";
export { Timeline } from "./timeline";
export type { TimelineToolComponent, TimelineToolProps } from "./tool-registry/types";
export { TurnActivity } from "./turn-activity";
export type { ItemStatus } from "./types";
