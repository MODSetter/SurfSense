"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import {
	currentThreadAtom,
	patchCurrentThreadMetadataAtom,
	resetCurrentThreadAtom,
} from "@/atoms/chat/current-thread.atom";
import {
	moveThreadArchiveState,
	patchThreadEverywhere,
	removeThreadEverywhere,
	replaceThreadEverywhere,
} from "@/lib/chat/thread-cache";
import {
	type ChatVisibility,
	deleteThread,
	type ThreadRecord,
	updateThread,
	updateThreadVisibility,
} from "@/lib/chat/thread-persistence";

type WorkspaceKey = number | string;

interface VisibilityVariables {
	thread: ThreadRecord;
	visibility: ChatVisibility;
}

interface RenameVariables {
	threadId: number;
	title: string;
	previousTitle?: string;
}

interface ArchiveVariables {
	threadId: number;
	archived: boolean;
}

interface DeleteVariables {
	threadId: number;
}

interface VisibilityRollback {
	threadId: number;
	visibility: ChatVisibility;
}

interface RenameRollback {
	threadId: number;
	title?: string;
}

interface ArchiveRollback {
	threadId: number;
	archived: boolean;
}

export function useUpdateThreadVisibility(workspaceId: WorkspaceKey) {
	const queryClient = useQueryClient();
	const currentThread = useAtomValue(currentThreadAtom);
	const patchCurrentThreadMetadata = useSetAtom(patchCurrentThreadMetadataAtom);

	return useMutation<ThreadRecord, Error, VisibilityVariables, VisibilityRollback>({
		mutationFn: ({ thread, visibility }) => updateThreadVisibility(thread.id, visibility),
		onMutate: ({ thread, visibility }) => {
			const previousVisibility = thread.visibility ?? "PRIVATE";

			patchThreadEverywhere(queryClient, workspaceId, thread.id, { visibility });
			if (currentThread.id === thread.id) {
				patchCurrentThreadMetadata({ id: thread.id, visibility });
			}

			return { threadId: thread.id, visibility: previousVisibility };
		},
		onError: (_error, _variables, rollback) => {
			if (!rollback) return;
			patchThreadEverywhere(queryClient, workspaceId, rollback.threadId, {
				visibility: rollback.visibility,
			});
			if (currentThread.id === rollback.threadId) {
				patchCurrentThreadMetadata({
					id: rollback.threadId,
					visibility: rollback.visibility,
				});
			}
		},
		onSuccess: (thread) => {
			replaceThreadEverywhere(queryClient, workspaceId, thread);
			if (currentThread.id === thread.id) {
				patchCurrentThreadMetadata({
					id: thread.id,
					visibility: thread.visibility,
					...(thread.has_comments !== undefined ? { hasComments: thread.has_comments } : {}),
				});
			}
		},
	});
}

export function useRenameThread(workspaceId: WorkspaceKey) {
	const queryClient = useQueryClient();

	return useMutation<ThreadRecord, Error, RenameVariables, RenameRollback>({
		mutationFn: ({ threadId, title }) => updateThread(threadId, { title }),
		onMutate: ({ threadId, title, previousTitle }) => {
			patchThreadEverywhere(queryClient, workspaceId, threadId, { title });
			return { threadId, title: previousTitle };
		},
		onError: (_error, _variables, rollback) => {
			if (!rollback || rollback.title === undefined) return;
			patchThreadEverywhere(queryClient, workspaceId, rollback.threadId, {
				title: rollback.title,
			});
		},
		onSuccess: (thread) => {
			replaceThreadEverywhere(queryClient, workspaceId, thread);
		},
	});
}

export function useArchiveThread(workspaceId: WorkspaceKey) {
	const queryClient = useQueryClient();

	return useMutation<ThreadRecord, Error, ArchiveVariables, ArchiveRollback>({
		mutationFn: ({ threadId, archived }) => updateThread(threadId, { archived }),
		onMutate: ({ threadId, archived }) => {
			moveThreadArchiveState(queryClient, workspaceId, threadId, archived);
			return { threadId, archived: !archived };
		},
		onError: (_error, _variables, rollback) => {
			if (!rollback) return;
			moveThreadArchiveState(queryClient, workspaceId, rollback.threadId, rollback.archived);
		},
		onSuccess: (thread) => {
			replaceThreadEverywhere(queryClient, workspaceId, thread);
			moveThreadArchiveState(queryClient, workspaceId, thread.id, thread.archived);
		},
	});
}

export function useDeleteThread(workspaceId: WorkspaceKey) {
	const queryClient = useQueryClient();
	const currentThread = useAtomValue(currentThreadAtom);
	const resetCurrentThread = useSetAtom(resetCurrentThreadAtom);

	return useMutation<void, Error, DeleteVariables>({
		mutationFn: ({ threadId }) => deleteThread(threadId),
		onSuccess: (_data, { threadId }) => {
			removeThreadEverywhere(queryClient, workspaceId, threadId);
			if (currentThread.id === threadId) {
				resetCurrentThread();
			}
		},
	});
}
