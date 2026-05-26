"use client";

import { useQuery as useZeroQuery } from "@rocicorp/zero/react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
	BookOpen,
	ChevronLeft,
	ChevronRight,
	Files,
	Folder as FolderIcon,
	Plug,
} from "lucide-react";
import {
	forwardRef,
	useCallback,
	useDeferredValue,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import type * as React from "react";
import {
	FOLDER_MENTION_DOCUMENT_TYPE,
	type MentionedDocumentInfo,
} from "@/atoms/chat/mentioned-documents.atom";
import { useAtomValue } from "jotai";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import {
	COMPOSIO_CONNECTORS,
	OAUTH_CONNECTORS,
} from "@/components/assistant-ui/connector-popup/constants/connector-constants";
import { getConnectorDisplayName } from "@/components/assistant-ui/connector-popup/tabs/all-connectors-tab";
import {
	ComposerSuggestionGroup,
	ComposerSuggestionGroupHeading,
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

type BrowseView =
	| { kind: "root" }
	| { kind: "surfsense-docs" }
	| { kind: "files-folders" }
	| { kind: "connectors" }
	| { kind: "connector-type"; connectorType: string; title: string };

type ResourceNodeValue =
	| { kind: "view"; view: BrowseView }
	| { kind: "mention"; mention: MentionedDocumentInfo };

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

function titleForConnectorType(connectorType: string) {
	const configured =
		OAUTH_CONNECTORS.find((c) => c.connectorType === connectorType) ||
		COMPOSIO_CONNECTORS.find((c) => c.connectorType === connectorType);
	return (
		configured?.title ||
		connectorType
			.replace(/_/g, " ")
			.replace(/connector/gi, "")
			.trim()
	);
}

function makeDocMention(doc: Pick<Document, "id" | "title" | "document_type">): MentionedDocumentInfo {
	return {
		id: doc.id,
		title: doc.title,
		document_type: doc.document_type,
		kind: "doc",
	};
}

function makeFolderMention(folder: { id: number; title: string }): MentionedDocumentInfo {
	return {
		id: folder.id,
		title: folder.title,
		document_type: FOLDER_MENTION_DOCUMENT_TYPE,
		kind: "folder",
	};
}

function makeConnectorMention(connector: SearchSourceConnector): MentionedDocumentInfo {
	const accountName = getConnectorDisplayName(connector.name);
	const connectorTitle = titleForConnectorType(connector.connector_type);
	return {
		id: connector.id,
		title: `${connectorTitle}: ${accountName}`,
		document_type: connector.connector_type,
		kind: "connector",
		connector_type: connector.connector_type,
		account_name: accountName,
	};
}

function mentionMatchesSearch(mention: MentionedDocumentInfo, searchLower: string) {
	return [
		mention.title,
		mention.document_type,
		mention.kind,
		mention.kind === "connector" ? mention.connector_type : "",
		mention.kind === "connector" ? mention.account_name : "",
	].some((value) => value.toLowerCase().includes(searchLower));
}

export const DocumentMentionPicker = forwardRef<
	DocumentMentionPickerRef,
	DocumentMentionPickerProps
>(function DocumentMentionPicker(
	{ searchSpaceId, onSelectionChange, onDone, initialSelectedDocuments = [], externalSearch = "" },
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

	const [zeroFolders] = useZeroQuery(queries.folders.bySpace({ searchSpaceId }));
	const { data: connectors = [], isLoading: isConnectorsLoading } = useAtomValue(connectorsAtom);
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

	const titleSearchParams = useMemo(
		() => ({
			search_space_id: searchSpaceId,
			page: 0,
			page_size: PAGE_SIZE,
			...(isSearchValid ? { title: debouncedSearch.trim() } : {}),
		}),
		[searchSpaceId, debouncedSearch, isSearchValid]
	);

	const surfsenseDocsQueryParams = useMemo(() => {
		const params: { page: number; page_size: number; title?: string } = {
			page: 0,
			page_size: PAGE_SIZE,
		};
		if (isSearchValid) params.title = debouncedSearch.trim();
		return params;
	}, [debouncedSearch, isSearchValid]);

	const { data: titleSearchResults, isLoading: isTitleSearchLoading } = useQuery({
		queryKey: ["document-titles", titleSearchParams],
		queryFn: ({ signal }) =>
			documentsApiService.searchDocumentTitles({ queryParams: titleSearchParams }, signal),
		staleTime: 60 * 1000,
		enabled: !!searchSpaceId && currentPage === 0 && (!hasSearch || isSearchValid),
		placeholderData: keepPreviousData,
	});

	const { data: surfsenseDocs, isLoading: isSurfsenseDocsLoading } = useQuery({
		queryKey: ["surfsense-docs-mention", debouncedSearch, isSearchValid],
		queryFn: ({ signal }) =>
			documentsApiService.getSurfsenseDocs({ queryParams: surfsenseDocsQueryParams }, signal),
		staleTime: 3 * 60 * 1000,
		enabled: !hasSearch || isSearchValid,
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

		if (surfsenseDocs?.items) {
			for (const doc of surfsenseDocs.items) {
				combinedDocs.push({
					id: doc.id,
					title: doc.title,
					document_type: "SURFSENSE_DOCS",
				});
			}
		}

		if (titleSearchResults?.items) {
			combinedDocs.push(...titleSearchResults.items);
			setHasMore(titleSearchResults.has_more);
		}

		setAccumulatedDocuments(filterBySearchTerm(combinedDocs));
	}, [titleSearchResults, surfsenseDocs, currentPage, filterBySearchTerm]);

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
			const response: SearchDocumentTitlesResponse = await documentsApiService.searchDocumentTitles({
				queryParams,
			});

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

	const surfsenseDocsList = useMemo(
		() => actualDocuments.filter((doc) => doc.document_type === "SURFSENSE_DOCS"),
		[actualDocuments]
	);
	const userDocsList = useMemo(
		() => actualDocuments.filter((doc) => doc.document_type !== "SURFSENSE_DOCS"),
		[actualDocuments]
	);
	const folderMentions = useMemo(() => {
		const all = (zeroFolders ?? []).map((f) => makeFolderMention({ id: f.id, title: f.name }));
		if (!hasSearch) return all;
		const needle = (isSingleCharSearch ? deferredSearch : debouncedSearch).trim().toLowerCase();
		if (!needle) return all;
		return all.filter((f) => f.title.toLowerCase().includes(needle));
	}, [zeroFolders, debouncedSearch, deferredSearch, isSingleCharSearch, hasSearch]);

	const connectorMentions = useMemo(
		() => connectors.filter((c) => c.is_active).map(makeConnectorMention),
		[connectors]
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

	const rootNodes = useMemo<ComposerSuggestionNode<ResourceNodeValue>[]>(
		() => [
			{
				id: "surfsense-docs",
				label: "SurfSense Docs",
				subtitle: "Browse product documentation",
				icon: <BookOpen className="size-4" />,
				type: "branch",
				value: { kind: "view", view: { kind: "surfsense-docs" } },
			},
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
				subtitle: connectors.length
					? "Choose the exact account for tool use"
					: "No connected accounts yet",
				icon: <Plug className="size-4" />,
				type: "branch",
				disabled: connectors.length === 0,
				value: { kind: "view", view: { kind: "connectors" } },
			},
		],
		[connectors.length]
	);

	const searchNodes = useMemo<ComposerSuggestionNode<ResourceNodeValue>[]>(() => {
		const searchLower = (isSingleCharSearch ? deferredSearch : debouncedSearch).trim().toLowerCase();
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
				icon: getConnectorIcon(mention.document_type, "size-4") ?? <Plug className="size-4" />,
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
		for (const connector of connectors.filter((c) => c.is_active)) {
			const list = byType.get(connector.connector_type) ?? [];
			list.push(connector);
			byType.set(connector.connector_type, list);
		}
		return Array.from(byType.entries()).sort(([a], [b]) =>
			titleForConnectorType(a).localeCompare(titleForConnectorType(b))
		);
	}, [connectors]);

	const browseNodes = useMemo<ComposerSuggestionNode<ResourceNodeValue>[]>(() => {
		if (view.kind === "root") return rootNodes;
		if (view.kind === "surfsense-docs") {
			return surfsenseDocsList.map((doc) => {
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
		}
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
			const docs = userDocsList.map((doc) => {
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
				label: titleForConnectorType(connectorType),
				subtitle: `${typeConnectors.length} ${typeConnectors.length === 1 ? "account" : "accounts"}`,
				icon: getConnectorIcon(connectorType, "size-4") ?? <Plug className="size-4" />,
				type: "branch" as const,
				value: {
					kind: "view" as const,
					view: {
						kind: "connector-type" as const,
						connectorType,
						title: titleForConnectorType(connectorType),
					},
				},
			}));
		}
		return connectors
			.filter((connector) => connector.is_active && connector.connector_type === view.connectorType)
			.map((connector) => {
				const mention = makeConnectorMention(connector);
				return {
					id: getMentionDocKey(mention),
					label: getConnectorDisplayName(connector.name),
					subtitle: `${view.title} account`,
					icon: getConnectorIcon(connector.connector_type, "size-4") ?? <Plug className="size-4" />,
					type: "item" as const,
					disabled: selectedKeys.has(getMentionDocKey(mention)),
					value: { kind: "mention" as const, mention },
				};
			});
	}, [
		connectors,
		connectorTypeEntries,
		folderMentions,
		rootNodes,
		selectedKeys,
		surfsenseDocsList,
		userDocsList,
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

	const handleScroll = useCallback(
		(e: React.UIEvent<HTMLDivElement>) => {
			if (view.kind === "connectors" || view.kind === "connector-type") return;
			const target = e.currentTarget;
			const scrollBottom = target.scrollHeight - target.scrollTop - target.clientHeight;

			if (scrollBottom < 50 && hasMore && !isLoadingMore) {
				loadNextPage();
			}
		},
		[hasMore, isLoadingMore, loadNextPage, view.kind]
	);

	const actualLoading =
		(isTitleSearchLoading || isSurfsenseDocsLoading || isConnectorsLoading) &&
		!isSingleCharSearch &&
		visibleNodes.length === 0 &&
		(view.kind === "root" || hasSearch);

	const title =
		hasSearch || view.kind === "root"
			? null
			: view.kind === "surfsense-docs"
				? "SurfSense Docs"
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
		>
			{actualLoading ? (
				<ComposerSuggestionSkeleton />
			) : (
				<ComposerSuggestionGroup>
					{title ? (
						<>
							<ComposerSuggestionItem
								icon={<ChevronLeft className="size-4" />}
								muted
								onClick={handleBack}
							>
								<span className="flex-1 truncate text-sm">{title}</span>
							</ComposerSuggestionItem>
							<ComposerSuggestionSeparator />
						</>
					) : null}

					{visibleNodes.length > 0 ? (
						<>
							{hasSearch ? (
								<ComposerSuggestionGroupHeading>Suggested Context</ComposerSuggestionGroupHeading>
							) : null}
							{visibleNodes.map((node, index) => (
								<ComposerSuggestionItem
									key={node.id}
									ref={navigator.getItemRef(index)}
									icon={node.icon}
									selected={index === navigator.highlightedIndex}
									disabled={node.disabled}
									onClick={() => !node.disabled && handleNodeSelect(node)}
									onMouseEnter={() => navigator.setHighlightedIndex(index)}
								>
									<span className="min-w-0 flex-1">
										<span className="block truncate text-sm" title={node.label}>
											{node.label}
										</span>
										{node.subtitle ? (
											<span className="block truncate text-[11px] text-muted-foreground">
												{node.subtitle}
											</span>
										) : null}
									</span>
									{node.type === "branch" ? (
										<ChevronRight className="size-4 shrink-0 text-muted-foreground" />
									) : null}
								</ComposerSuggestionItem>
							))}
						</>
					) : (
						<ComposerSuggestionMessage>
							{hasSearch ? "No matching context" : "No items available"}
						</ComposerSuggestionMessage>
					)}

					{isLoadingMore && (
						<div className="flex items-center justify-center py-2 text-primary">
							<Spinner size="sm" />
						</div>
					)}
				</ComposerSuggestionGroup>
			)}
		</ComposerSuggestionList>
	);
});
