import type { TimelineGroup, TimelineItem } from "./types";

/**
 * Group delegated child items under their owning ``task`` parent.
 *
 * Backend invariant: ``metadata.spanId`` is set only while a ``task``
 * tool is open, so every non-task item with ``spanId = X`` shares it
 * with the ``task`` that owns the span. We promote that task to the
 * group header.
 *
 * The owner-missing branch defends against the live-resume window
 * where the OLD ``task`` wrapper can be superseded while its
 * children briefly survive — without it, grouping would promote
 * the first orphan child to parent and visually nest its siblings
 * under it.
 */
export function groupItems(items: readonly TimelineItem[]): TimelineGroup[] {
	const spanOwners = new Set<string>();
	for (const item of items) {
		if (item.kind === "tool-call" && item.toolName === "task" && item.spanId) {
			spanOwners.add(item.spanId);
		}
	}

	const groups: TimelineGroup[] = [];
	const spanParent = new Map<string, TimelineGroup>();

	for (const item of items) {
		const sid = item.spanId;
		if (!sid || !spanOwners.has(sid)) {
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
