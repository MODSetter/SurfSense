import type { TimelineGroup, TimelineItem } from "./types";

/**
 * Group consecutive delegated child items under their parent.
 *
 * The contract: the parent of a span is the FIRST item carrying that
 * ``spanId``. Subsequent items with the same ``spanId`` are children.
 * Items with no ``spanId`` are their own parent (no children).
 *
 * For ``task`` delegations specifically, the ``task`` tool-call IS the
 * span owner — its ``spanId`` is set on the call itself, and child
 * items emitted while the subagent is running carry the same ``spanId``.
 * The ``task`` item must therefore become the parent header, NOT a
 * child of itself. This is achieved by treating the FIRST occurrence
 * of any ``spanId`` as the parent; downstream items with the same
 * ``spanId`` are children.
 *
 * Defensive: if the very first item of a stream is a child of a span
 * we haven't seen the parent for yet, it's promoted to a parent so it
 * still renders. Real flows always emit the parent ``task`` first.
 *
 * Pure function. No React, no side effects. Trivially testable.
 */
export function groupItems(items: readonly TimelineItem[]): TimelineGroup[] {
	const groups: TimelineGroup[] = [];
	const spanParent = new Map<string, TimelineGroup>();

	for (const item of items) {
		const sid = item.spanId;
		if (!sid) {
			groups.push({ parent: item, children: [] });
			continue;
		}

		const existing = spanParent.get(sid);
		if (existing) {
			existing.children.push(item);
			continue;
		}

		const group: TimelineGroup = { parent: item, children: [] };
		groups.push(group);
		spanParent.set(sid, group);
	}

	return groups;
}
