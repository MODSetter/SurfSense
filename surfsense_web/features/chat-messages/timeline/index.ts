/**
 * Public surface of the ``timeline/`` slice.
 *
 * Message renderers consume the interleaved trace here. The tool registry
 * remains internal except for its narrow HITL body contract.
 */

export { InterleavedMessageParts, TraceItemRow } from "./interleaved-trace";
export type { TimelineToolComponent, TimelineToolProps } from "./tool-registry/types";
export type { ItemStatus } from "./types";
