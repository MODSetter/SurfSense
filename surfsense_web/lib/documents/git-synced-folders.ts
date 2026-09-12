import type { GitRemote } from "@/contracts/types/git-remote.types";
import type { FolderDisplay } from "@/lib/documents/document-tree-types";

/** `owner/repo` from a forge clone URL, for display only. */
export function gitRepoLabel(remote: GitRemote): string {
	let path = remote.url.trim();
	const scheme = path.indexOf("://");
	if (scheme !== -1) {
		const afterScheme = path.slice(scheme + 3);
		const firstSlash = afterScheme.indexOf("/");
		path = firstSlash === -1 ? "" : afterScheme.slice(firstSlash + 1);
	}
	path = path.replace(/^\/+|\/+$/g, "");
	if (path.toLowerCase().endsWith(".git")) path = path.slice(0, -4);
	return path;
}

/** Backend-resolved mount folder id, or null until the folder exists. */
export function gitMountFolderId(remote: GitRemote | undefined): number | null {
	return remote?.mount_folder_id ?? null;
}

/** True if `ancestorId` is `folderId` itself or any of its ancestors. */
function isSelfOrDescendantOf(
	byId: Map<number, FolderDisplay>,
	folderId: number,
	ancestorId: number
): boolean {
	let cursor: FolderDisplay | undefined = byId.get(folderId);
	const seen = new Set<number>();
	while (cursor && !seen.has(cursor.id)) {
		if (cursor.id === ancestorId) return true;
		seen.add(cursor.id);
		cursor = cursor.parentId != null ? byId.get(cursor.parentId) : undefined;
	}
	return false;
}

/** True if `folderId` is the mount folder or lives inside it (i.e. synced). */
export function isSyncedContent(
	folders: FolderDisplay[],
	folderId: number | null | undefined,
	mountId: number | null
): boolean {
	if (mountId == null || folderId == null) return false;
	const byId = new Map(folders.map((f) => [f.id, f]));
	return isSelfOrDescendantOf(byId, folderId, mountId);
}

/** True if deleting `folderId` would reach the mount: it is, contains, or lives inside it. */
export function folderDeletionTouchesSync(
	folders: FolderDisplay[],
	folderId: number,
	mountId: number | null
): boolean {
	if (mountId == null) return false;
	const byId = new Map(folders.map((f) => [f.id, f]));
	return (
		isSelfOrDescendantOf(byId, folderId, mountId) ||
		isSelfOrDescendantOf(byId, mountId, folderId)
	);
}
