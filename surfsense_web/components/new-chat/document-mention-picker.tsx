"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { ChevronLeft, ChevronRight, Files, Folder as FolderIcon, Unplug } from "lucide-react";
import {
	Fragment,
	forwardRef,
	type UIEvent,
	useCallback,
	useDeferredValue,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import type { MentionedDocumentInfo } from "@/atoms/chat/mentioned-documents.atom";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { getConnectorTitle } from "@/components/assistant-ui/connector-popup/constants/connector-constants";
import { getConnectorDisplayName } from "@/components/assistant-ui/connector-popup/tabs/all-connectors-tab";
import {
	ComposerSuggestionGroup,
	ComposerSuggestionGroupHeading,
	ComposerSuggestionHeader,
	ComposerSuggestionItem,
	ComposerSuggestionList,
	ComposerSuggestionMessage,
	ComposerSuggestionSeparator,
	ComposerSuggestionSkeleton,
} from "@/components/new-chat/composer-suggestion-popup";
import {
	type ComposerSuggestionNavigatorRef,
	type ComposerSuggestionNode,
	useComposerSuggestionNavigator,
} from "@/components/new-chat/use-composer-suggestion-navigator";
import { Spinner } from "@/components/ui/spinner";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { Document, SearchDocumentTitlesResponse } from "@/contracts/types/document.types";
import { documentsApiService } from "@/lib/apis/documents-api.service";
import { getMentionDocKey } from "@/lib/chat/mention-doc-key";
import { queries } from "@/zero/queries";

export type DocumentMentionPickerRef = ComposerSuggestionNavigatorRef;

interface DocumentMentionPickerProps {
	searchSpaceId: number;
	onSelectionChange: (mentions: MentionedDocumentInfo[]) => void;
	onDone: () => void;
	initialSelectedDocuments?: MentionedDocumentInfo[];
	externalSearch?: string;
}

const PAGE_SIZE = 20;
const MIN_SEARCH_LENGTH = 2;
const DEBOUNCE_MS = 100;
const RECENTS_LIMIT = 3;
const RECENTS_STORAGE_PREFIX = "surfsense:composer-mention-recents:v1:";

type BrowseView =
	| { kind: "root" }
	| { kind: "files-folders" }
	| { kind: "connectors" }
	| { kind: "connector-type"; connectorType: string; title: string };

type ResourceNodeValue =
	| { kind: "view"; view: BrowseView }
	| { kind: "mention"; mention: MentionedDocumentInfo };

function isConnectorActive(connector: SearchSourceConnector) {
	return connector.is_active !== false;
}

function isMentionedContextItem(value: unknown): value is MentionedDocumentInfo {
	if (!value || typeof value !== "object") return false;
	const item = value as Partial<MentionedDocumentInfo>;
	if (typeof item.id !== "number" || typeof item.title !== "string") return false;
	if (item.kind === "doc") return typeof item.document_type === "string";
	if (item.kind === "folder") return true;
	if (item.kind === "connector") {
		return typeof item.connector_type === "string" && typeof item.account_name === "string";
	}
	return false;
}

function getRecentsStorageKey(searchSpaceId: number) {
	return `${RECENTS_STORAGE_PREFIX}${searchSpaceId}`;
}

function readRecentMentions(searchSpaceId: number): MentionedDocumentInfo[] {
	if (typeof window === "undefined") return [];
	try {
		const raw = window.localStorage.getItem(getRecentsStorageKey(searchSpaceId));
		if (!raw) return [];
		const parsed: unknown = JSON.parse(raw);
		if (!Array.isArray(parsed)) return [];
		return parsed.filter(isMentionedContextItem).slice(0, RECENTS_LIMIT);
	} catch {
		return [];
	}
}

function writeRecentMentions(searchSpaceId: number, mentions: MentionedDocumentInfo[]) {
	if (typeof window === "undefined") return;
	try {
		window.localStorage.setItem(
			getRecentsStorageKey(searchSpaceId),
			JSON.stringify(mentions.slice(0, RECENTS_LIMIT))
		);
	} catch {
		// Recents are optional UI state; storage failures should not block mention insertion.
	}
}

export function promoteRecentMention(searchSpaceId: number, mention: MentionedDocumentInfo) {
	const mentionKey = getMentionDocKey(mention);
	const next = [
		mention,
		...readRecentMentions(searchSpaceId).filter((item) => getMentionDocKey(item) !== mentionKey),
	].slice(0, RECENTS_LIMIT);
	writeRecentMentions(searchSpaceId, next);
	return next;
}

function getMentionIcon(mention: MentionedDocumentInfo) {
	if (mention.kind === "folder") return <FolderIcon className="size-4" />;
	if (mention.kind === "connector") {
		return getConnectorIcon(mention.connector_type, "size-4") ?? <Unplug className="size-4" />;
	}
	return getConnectorIcon(mention.document_type, "size-4");
}

function refreshRecentMention(
	mention: MentionedDocumentInfo,
	documents: Pick<Document, "id" | "title" | "document_type">[],
	folders: { id: number; name: string }[],
	connectors: SearchSourceConnector[],
	hasHydratedRecentDocs: boolean
): MentionedDocumentInfo | null {
	if (mention.kind === "doc") {
		const doc = documents.find(
			(item) => item.id === mention.id && item.document_type === mention.document_type
		);
		if (doc) return makeDocMention(doc);
		return hasHydratedRecentDocs ? null : mention;
	}
	if (mention.kind === "folder") {
		const folder = folders.find((item) => item.id === mention.id);
		return folder ? makeFolderMention({ id: folder.id, title: folder.name }) : null;
	}
	const connector = connectors.find(
		(item) => item.id === mention.id && item.connector_type === mention.connector_type
	);
	return connector ? makeConnectorMention(connector) : null;
}

function useDebounced<T>(value: T, delay = DEBOUNCE_MS) {
	const [debounced, setDebounced] = useState(value);
	const timeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

	useEffect(() => {
		if (timeoutRef.current) clearTimeout(timeoutRef.current);
		timeoutRef.current = setTimeout(() => setDebounced(value), delay);
		return () => {
			if (timeoutRef.current) clearTimeout(timeoutRef.current);
		};
	}, [value, delay]);

	return debounced;
}

function makeDocMention(
	doc: Pick<Document, "id" | "title" | "document_type">
): MentionedDocumentInfo {
	return {
		id: doc.id,
		title: doc.title,
		document_type: doc.document_type,
		kind: "doc",
	};
}

function makeFolderMention(folder: {
	id: number;
	title: string;
}): Extract<MentionedDocumentInfo, { kind: "folder" }> {
	return {
		id: folder.id,
		title: folder.title,
		kind: "folder",
	};
}

function makeConnectorMention(
	connector: SearchSourceConnector
): Extract<MentionedDocumentInfo, { kind: "connector" }> {
	const accountName = getConnectorDisplayName(connector.name);
	const connectorTitle = getConnectorTitle(connector.connector_type);
	return {
		id: connector.id,
		title: `${connectorTitle}: ${accountName}`,
		kind: "connector",
		connector_type: connector.connector_type,
		account_name: accountName,
	};
}

function mentionMatchesSearch(mention: MentionedDocumentInfo, searchLower: string) {
	return [
		mention.title,
		mention.kind,
		mention.kind === "doc" ? mention.document_type : "",
		mention.kind === "connector" ? mention.connector_type : "",
		mention.kind === "connector" ? mention.account_name : "",
	].some((value) => value.toLowerCase().includes(searchLower));
}

export const DocumentMentionPicker = forwardRef<
	DocumentMentionPickerRef,
	DocumentMentionPickerProps
>(function DocumentMentionPicker(
	{
		searchSpaceId,
		onSelectionChange,
		onDone,
		initialSelectedDocuments = [],
		externalSearch = "",
	},
	ref
) {
	const search = externalSearch;
	const debouncedSearch = useDebounced(search, DEBOUNCE_MS);
	const deferredSearch = useDeferredValue(debouncedSearch);
	const hasSearch = debouncedSearch.trim().length > 0;
	const isSearchValid = debouncedSearch.trim().length >= MIN_SEARCH_LENGTH;
	const isSingleCharSearch = debouncedSearch.trim().length === 1;
	const [view, setView] = useState<BrowseView>({ kind: "root" });

	const [accumulatedDocuments, setAccumulatedDocuments] = useState<
		Pick<Document, "id" | "title" | "document_type">[]
	>([]);
	const [currentPage, setCurrentPage] = useState(0);
	const [hasMore, setHasMore] = useState(false);
	const [isLoadingMore, setIsLoadingMore] = useState(false);
	const [recentMentions, setRecentMentions] = useState<MentionedDocumentInfo[]>(() =>
		readRecentMentions(searchSpaceId)
	);

	const [zeroFolders] = useZeroQuery(queries.folders.bySpace({ searchSpaceId }));
	const { data: connectors = [], isLoading: isConnectorsLoading } = useAtomValue(connectorsAtom);
	const activeConnectors = useMemo(() => connectors.filter(isConnectorActive), [connectors]);
	const paginationScopeKey = useMemo(
		() => `${searchSpaceId}:${debouncedSearch}`,
		[searchSpaceId, debouncedSearch]
	);
	const previousPaginationScopeKeyRef = useRef<string | null>(null);

	// Reset pagination state when the active search scope changes.
	useEffect(() => {
		if (previousPaginationScopeKeyRef.current === paginationScopeKey) return;
		previousPaginationScopeKeyRef.current = paginationScopeKey;
		setCurrentPage(0);
		setHasMore(false);
	}, [paginationScopeKey]);

	useEffect(() => {
		if (hasSearch) setView({ kind: "root" });
	}, [hasSearch]);

	useEffect(() => {
		setRecentMentions(readRecentMentions(searchSpaceId));
	}, [searchSpaceId]);

	const titleSearchParams = useMemo(
		() => ({
			search_space_id: searchSpaceId,
			page: 0,
			page_size: PAGE_SIZE,
			...(isSearchValid ? { title: debouncedSearch.trim() } : {}),
		}),
		[searchSpaceId, debouncedSearch, isSearchValid]
	);

	const { data: titleSearchResults, isLoading: isTitleSearchLoading } = useQuery({
		queryKey: ["document-titles", titleSearchParams],
		queryFn: ({ signal }) =>
			documentsApiService.searchDocumentTitles({ queryParams: titleSearchParams }, signal),
		staleTime: 60 * 1000,
		enabled: !!searchSpaceId && currentPage === 0 && (!hasSearch || isSearchValid),
		placeholderData: keepPreviousData,
	});

	const filterBySearchTerm = useCallback(
		(docs: Pick<Document, "id" | "title" | "document_type">[]) => {
			if (!isSearchValid) return docs;
			const searchLower = debouncedSearch.trim().toLowerCase();
			return docs.filter((doc) => doc.title.toLowerCase().includes(searchLower));
		},
		[debouncedSearch, isSearchValid]
	);

	useEffect(() => {
		if (currentPage !== 0) return;
		const combinedDocs: Pick<Document, "id" | "title" | "document_type">[] = [];

		if (titleSearchResults?.items) {
			combinedDocs.push(...titleSearchResults.items);
			setHasMore(titleSearchResults.has_more);
		}

		setAccumulatedDocuments(filterBySearchTerm(combinedDocs));
	}, [titleSearchResults, currentPage, filterBySearchTerm]);

	const loadNextPage = useCallback(async () => {
		if (isLoadingMore || !hasMore) return;

		const nextPage = currentPage + 1;
		setIsLoadingMore(true);

		try {
			const queryParams = {
				search_space_id: searchSpaceId,
				page: nextPage,
				page_size: PAGE_SIZE,
				...(isSearchValid ? { title: debouncedSearch.trim() } : {}),
			};
			const response: SearchDocumentTitlesResponse = await documentsApiService.searchDocumentTitles(
				{
					queryParams,
				}
			);

			setAccumulatedDocuments((prev) => [...prev, ...response.items]);
			setHasMore(response.has_more);
			setCurrentPage(nextPage);
		} catch (error) {
			console.error("Failed to load next page:", error);
		} finally {
			setIsLoadingMore(false);
		}
	}, [currentPage, hasMore, isLoadingMore, debouncedSearch, searchSpaceId, isSearchValid]);

	const actualDocuments = useMemo(() => {
		if (!isSingleCharSearch) return accumulatedDocuments;
		const searchLower = deferredSearch.trim().toLowerCase();
		return accumulatedDocuments.filter((doc) => doc.title.toLowerCase().includes(searchLower));
	}, [accumulatedDocuments, deferredSearch, isSingleCharSearch]);

	const folderMentions = useMemo(() => {
		const all = (zeroFolders ?? []).map((f) => makeFolderMention({ id: f.id, title: f.name }));
		if (!hasSearch) return all;
		const needle = (isSingleCharSearch ? deferredSearch : debouncedSearch).trim().toLowerCase();
		if (!needle) return all;
		return all.filter((f) => f.title.toLowerCase().includes(needle));
	}, [zeroFolders, debouncedSearch, deferredSearch, isSingleCharSearch, hasSearch]);

	const connectorMentions = useMemo(
		() => activeConnectors.map(makeConnectorMention),
		[activeConnectors]
	);
	const recentDocMentions = useMemo(
		() => recentMentions.filter((mention) => mention.kind === "doc"),
		[recentMentions]
	);
	const recentDocIdsKey = useMemo(
		() => recentDocMentions.map((mention) => mention.id).join(","),
		[recentDocMentions]
	);
	const { data: hydratedRecentDocs = [], isFetched: hasHydratedRecentDocs } = useQuery({
		queryKey: ["composer-mention-recent-docs", searchSpaceId, recentDocIdsKey],
		queryFn: async () => {
			const results = await Promise.allSettled(
				recentDocMentions.map((mention) => documentsApiService.getDocument({ id: mention.id }))
			);
			return results
				.map((result) => (result.status === "fulfilled" ? result.value : null))
				.filter((doc): doc is Document => doc !== null);
		},
		enabled: recentDocMentions.length > 0,
		staleTime: 60 * 1000,
	});
	const recentValidationDocuments = useMemo(
		() => [...actualDocuments, ...hydratedRecentDocs],
		[actualDocuments, hydratedRecentDocs]
	);
	const visibleRecentMentions = useMemo(
		() =>
			recentMentions
				.map((mention) =>
					refreshRecentMention(
						mention,
						recentValidationDocuments,
						zeroFolders ?? [],
						activeConnectors,
						hasHydratedRecentDocs
					)
				)
				.filter((mention): mention is MentionedDocumentInfo => mention !== null)
				.slice(0, RECENTS_LIMIT),
		[
			activeConnectors,
			hasHydratedRecentDocs,
			recentMentions,
			recentValidationDocuments,
			zeroFolders,
		]
	);

	const selectedKeys = useMemo(
		() => new Set(initialSelectedDocuments.map((d) => getMentionDocKey(d))),
		[initialSelectedDocuments]
	);

	const selectMention = useCallback(
		(mention: MentionedDocumentInfo) => {
			onSelectionChange([...initialSelectedDocuments, mention]);
			onDone();
		},
		[initialSelectedDocuments, onSelectionChange, onDone]
	);
	const recentRootNodes = useMemo<ComposerSuggestionNode<ResourceNodeValue>[]>(
		() =>
			visibleRecentMentions.map((mention) => ({
				id: `recent:${getMentionDocKey(mention)}`,
				label: mention.title,
				icon: getMentionIcon(mention),
				type: "item" as const,
				disabled: selectedKeys.has(getMentionDocKey(mention)),
				value: { kind: "mention" as const, mention },
			})),
		[visibleRecentMentions, selectedKeys]
	);

	const rootNodes = useMemo<ComposerSuggestionNode<ResourceNodeValue>[]>(() => {
		const nodes: ComposerSuggestionNode<ResourceNodeValue>[] = [...recentRootNodes];
		nodes.push(
			{
				id: "files-folders",
				label: "Files & Folders",
				subtitle: "Browse your knowledge base",
				icon: <Files className="size-4" />,
				type: "branch",
				value: { kind: "view", view: { kind: "files-folders" } },
			},
			{
				id: "connectors",
				label: "Connectors",
				subtitle: activeConnectors.length
					? "Choose the exact account for tool use"
					: "No connected accounts yet",
				icon: <Unplug className="size-4" />,
				type: "branch",
				disabled: activeConnectors.length === 0,
				value: { kind: "view", view: { kind: "connectors" } },
			}
		);
		return nodes;
	}, [activeConnectors.length, recentRootNodes]);

	const searchNodes = useMemo<ComposerSuggestionNode<ResourceNodeValue>[]>(() => {
		const searchLower = (isSingleCharSearch ? deferredSearch : debouncedSearch)
			.trim()
			.toLowerCase();
		const docNodes = actualDocuments.map((doc) => {
			const mention = makeDocMention(doc);
			return {
				id: getMentionDocKey(mention),
				label: doc.title,
				icon: getConnectorIcon(doc.document_type, "size-4"),
				type: "item" as const,
				disabled: selectedKeys.has(getMentionDocKey(mention)),
				value: { kind: "mention" as const, mention },
			};
		});
		const folderNodes = folderMentions.map((mention) => ({
			id: getMentionDocKey(mention),
			label: mention.title,
			subtitle: "Folder",
			icon: <FolderIcon className="size-4" />,
			type: "item" as const,
			disabled: selectedKeys.has(getMentionDocKey(mention)),
			value: { kind: "mention" as const, mention },
		}));
		const connectorNodes = connectorMentions
			.filter((mention) => !searchLower || mentionMatchesSearch(mention, searchLower))
			.map((mention) => ({
				id: getMentionDocKey(mention),
				label: mention.title,
				subtitle: "Connector account",
				icon: getConnectorIcon(mention.connector_type, "size-4") ?? <Unplug className="size-4" />,
				type: "item" as const,
				disabled: selectedKeys.has(getMentionDocKey(mention)),
				value: { kind: "mention" as const, mention },
			}));

		return [...docNodes, ...folderNodes, ...connectorNodes];
	}, [
		actualDocuments,
		connectorMentions,
		debouncedSearch,
		deferredSearch,
		folderMentions,
		isSingleCharSearch,
		selectedKeys,
	]);

	const connectorTypeEntries = useMemo(() => {
		const byType = new Map<string, SearchSourceConnector[]>();
		for (const connector of activeConnectors) {
			const list = byType.get(connector.connector_type) ?? [];
			list.push(connector);
			byType.set(connector.connector_type, list);
		}
		return Array.from(byType.entries()).sort(([a], [b]) =>
			getConnectorTitle(a).localeCompare(getConnectorTitle(b))
		);
	}, [activeConnectors]);

	const browseNodes = useMemo<ComposerSuggestionNode<ResourceNodeValue>[]>(() => {
		if (view.kind === "root") return rootNodes;
		if (view.kind === "files-folders") {
			const folders = folderMentions.map((mention) => ({
				id: getMentionDocKey(mention),
				label: mention.title,
				subtitle: "Folder",
				icon: <FolderIcon className="size-4" />,
				type: "item" as const,
				disabled: selectedKeys.has(getMentionDocKey(mention)),
				value: { kind: "mention" as const, mention },
			}));
			const docs = actualDocuments.map((doc) => {
				const mention = makeDocMention(doc);
				return {
					id: getMentionDocKey(mention),
					label: doc.title,
					icon: getConnectorIcon(doc.document_type, "size-4"),
					type: "item" as const,
					disabled: selectedKeys.has(getMentionDocKey(mention)),
					value: { kind: "mention" as const, mention },
				};
			});
			return [...folders, ...docs];
		}
		if (view.kind === "connectors") {
			return connectorTypeEntries.map(([connectorType, typeConnectors]) => ({
				id: `connector-type:${connectorType}`,
				label: getConnectorTitle(connectorType),
				subtitle: `${typeConnectors.length} ${typeConnectors.length === 1 ? "account" : "accounts"}`,
				icon: getConnectorIcon(connectorType, "size-4") ?? <Unplug className="size-4" />,
				type: "branch" as const,
				value: {
					kind: "view" as const,
					view: {
						kind: "connector-type" as const,
						connectorType,
						title: getConnectorTitle(connectorType),
					},
				},
			}));
		}
		return activeConnectors
			.filter((connector) => connector.connector_type === view.connectorType)
			.map((connector) => {
				const mention = makeConnectorMention(connector);
				return {
					id: getMentionDocKey(mention),
					label: getConnectorDisplayName(connector.name),
					subtitle: `${view.title} account`,
					icon: getConnectorIcon(connector.connector_type, "size-4") ?? (
						<Unplug className="size-4" />
					),
					type: "item" as const,
					disabled: selectedKeys.has(getMentionDocKey(mention)),
					value: { kind: "mention" as const, mention },
				};
			});
	}, [
		actualDocuments,
		activeConnectors,
		connectorTypeEntries,
		folderMentions,
		rootNodes,
		selectedKeys,
		view,
	]);

	const visibleNodes = hasSearch ? searchNodes : browseNodes;
	const handleNodeSelect = useCallback(
		(node: ComposerSuggestionNode<ResourceNodeValue>) => {
			const value = node.value;
			if (!value) return;
			if (value.kind === "view") {
				setView(value.view);
				return;
			}
			selectMention(value.mention);
		},
		[selectMention]
	);
	const handleBack = useCallback(() => {
		if (hasSearch || view.kind === "root") return false;
		if (view.kind === "connector-type") {
			setView({ kind: "connectors" });
			return true;
		}
		setView({ kind: "root" });
		return true;
	}, [hasSearch, view]);

	const navigator = useComposerSuggestionNavigator({
		nodes: visibleNodes,
		onSelect: handleNodeSelect,
		onBack: handleBack,
		ref,
	});
	const canLoadMoreDocuments = hasSearch || view.kind === "files-folders";

	const handleScroll = useCallback(
		(e: UIEvent<HTMLDivElement>) => {
			if (!canLoadMoreDocuments) return;
			const target = e.currentTarget;
			const scrollBottom = target.scrollHeight - target.scrollTop - target.clientHeight;

			if (scrollBottom < 50 && hasMore && !isLoadingMore) {
				loadNextPage();
			}
		},
		[canLoadMoreDocuments, hasMore, isLoadingMore, loadNextPage]
	);

	const isRootBrowseView = !hasSearch && view.kind === "root";
	const isVisibleViewLoading = hasSearch
		? isTitleSearchLoading || isConnectorsLoading
		: view.kind === "files-folders"
			? isTitleSearchLoading
			: view.kind === "connectors" || view.kind === "connector-type"
				? isConnectorsLoading
				: false;
	const actualLoading =
		isVisibleViewLoading && !isSingleCharSearch && visibleNodes.length === 0 && !isRootBrowseView;

	const title =
		hasSearch || view.kind === "root"
			? null
			: view.kind === "files-folders"
				? "Files & Folders"
				: view.kind === "connectors"
					? "Connectors"
					: view.title;

	return (
		<ComposerSuggestionList
			ref={navigator.scrollContainerRef}
			onScroll={handleScroll}
			role="listbox"
			tabIndex={-1}
			className={isRootBrowseView ? "max-h-none overflow-visible sm:max-h-none" : undefined}
		>
			{actualLoading ? (
				<ComposerSuggestionSkeleton rows={8} mobileRows={8} />
			) : (
				<ComposerSuggestionGroup>
					{title ? (
						<>
							<ComposerSuggestionHeader
								role="button"
								tabIndex={0}
								aria-label={`Back from ${title}`}
								onClick={handleBack}
								onKeyDown={(event) => {
									if (event.key === "Enter" || event.key === " ") {
										event.preventDefault();
										handleBack();
									}
								}}
								className="cursor-pointer rounded-sm transition-colors hover:text-foreground focus-visible:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
								icon={
									<span className="-ml-0.5 flex size-4.5 items-center justify-center">
										<ChevronLeft className="size-3.5" />
									</span>
								}
							>
								<span className="flex-1 truncate">{title}</span>
							</ComposerSuggestionHeader>
							<ComposerSuggestionSeparator />
						</>
					) : null}

					{visibleNodes.length > 0 ? (
						<>
							{hasSearch ? (
								<ComposerSuggestionGroupHeading>Suggested Context</ComposerSuggestionGroupHeading>
							) : null}
							{!hasSearch && view.kind === "root" && recentRootNodes.length > 0 ? (
								<ComposerSuggestionGroupHeading>Recents</ComposerSuggestionGroupHeading>
							) : null}
							{visibleNodes.map((node, index) => {
								const showRecentsSeparator =
									!hasSearch &&
									view.kind === "root" &&
									recentRootNodes.length > 0 &&
									index === recentRootNodes.length;
								return (
									<Fragment key={node.id}>
										{showRecentsSeparator ? <ComposerSuggestionSeparator /> : null}
										<ComposerSuggestionItem
											ref={navigator.getItemRef(index)}
											icon={node.icon}
											selected={index === navigator.highlightedIndex}
											disabled={node.disabled}
											onClick={() => !node.disabled && handleNodeSelect(node)}
											onMouseEnter={() => navigator.setHighlightedIndex(index)}
										>
											<span className="min-w-0 flex-1">
												<span className="block truncate text-xs" title={node.label}>
													{node.label}
												</span>
												{node.subtitle ? (
													<span className="block truncate text-[10px] text-muted-foreground">
														{node.subtitle}
													</span>
												) : null}
											</span>
											{node.type === "branch" ? (
												<ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
											) : null}
										</ComposerSuggestionItem>
									</Fragment>
								);
							})}
						</>
					) : (
						<ComposerSuggestionMessage>
							{hasSearch ? "No matching context" : "No items available"}
						</ComposerSuggestionMessage>
					)}

					{canLoadMoreDocuments && isLoadingMore && (
						<div className="flex items-center justify-center py-2 text-primary">
							<Spinner size="sm" />
						</div>
					)}
				</ComposerSuggestionGroup>
			)}
		</ComposerSuggestionList>
	);
});
