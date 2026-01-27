"use client";

import { ArrowRight, Cable } from "lucide-react";
import { useRouter } from "next/navigation";
import type { FC } from "react";
import { useState } from "react";
import { getDocumentTypeLabel } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentTypeIcon";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { TabsContent } from "@/components/ui/tabs";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import type { LogActiveTask, LogSummary } from "@/contracts/types/log.types";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";
import { cn } from "@/lib/utils";
import { COMPOSIO_CONNECTORS, OAUTH_CONNECTORS } from "../constants/connector-constants";
import { getDocumentCountForConnector } from "../utils/connector-document-mapping";
import { getConnectorDisplayName } from "./all-connectors-tab";

interface ActiveConnectorsTabProps {
	searchQuery: string;
	hasSources: boolean;
	totalSourceCount: number;
	activeDocumentTypes: Array<[string, number]>;
	connectors: SearchSourceConnector[];
	indexingConnectorIds: Set<number>;
	searchSpaceId: string;
	onTabChange: (value: string) => void;
	onManage?: (connector: SearchSourceConnector) => void;
	onViewAccountsList?: (connectorType: string, connectorTitle: string) => void;
}

/**
 * Check if a connector type is indexable
 */
function isIndexableConnector(connectorType: string): boolean {
	const nonIndexableTypes = ["MCP_CONNECTOR"];
	return !nonIndexableTypes.includes(connectorType);
}

export const ActiveConnectorsTab: FC<ActiveConnectorsTabProps> = ({
	searchQuery,
	hasSources,
	activeDocumentTypes,
	connectors,
	indexingConnectorIds,
	searchSpaceId,
	onTabChange,
	onManage,
	onViewAccountsList,
}) => {
	const router = useRouter();

	const handleViewAllDocuments = () => {
		router.push(`/dashboard/${searchSpaceId}/documents`);
	};

	// Convert activeDocumentTypes array to Record for utility function
	const documentTypeCounts = activeDocumentTypes.reduce(
		(acc, [docType, count]) => {
			acc[docType] = count;
			return acc;
		},
		{} as Record<string, number>
	);

	// Format document count (e.g., "1.2k docs", "500 docs", "1.5M docs")
	const formatDocumentCount = (count: number | undefined): string => {
		if (count === undefined || count === 0) return "0 docs";
		if (count < 1000) return `${count} docs`;
		if (count < 1000000) {
			const k = (count / 1000).toFixed(1);
			return `${k.replace(/\.0$/, "")}k docs`;
		}
		const m = (count / 1000000).toFixed(1);
		return `${m.replace(/\.0$/, "")}M docs`;
	};

	// Document types that should be shown as standalone cards (not from connectors)
	const standaloneDocumentTypes = ["EXTENSION", "FILE", "NOTE", "YOUTUBE_VIDEO", "CRAWLED_URL"];

	// Filter to only show standalone document types that have documents (count > 0)
	const standaloneDocuments = activeDocumentTypes
		.filter(([docType, count]) => standaloneDocumentTypes.includes(docType) && count > 0)
		.map(([docType, count]) => ({
			type: docType,
			count,
			label: getDocumentTypeLabel(docType),
		}))
		.filter((doc) => {
			if (!searchQuery) return true;
			return doc.label.toLowerCase().includes(searchQuery.toLowerCase());
		});

	// Get OAuth connector types set for quick lookup
	const oauthConnectorTypes = new Set<string>(OAUTH_CONNECTORS.map((c) => c.connectorType));

	// Separate OAuth and non-OAuth connectors
	const oauthConnectors = connectors.filter((c) => oauthConnectorTypes.has(c.connector_type));
	const nonOauthConnectors = connectors.filter((c) => !oauthConnectorTypes.has(c.connector_type));

	// Group OAuth connectors by type
	const oauthConnectorsByType = oauthConnectors.reduce(
		(acc, connector) => {
			const type = connector.connector_type;
			if (!acc[type]) {
				acc[type] = [];
			}
			acc[type].push(connector);
			return acc;
		},
		{} as Record<string, SearchSourceConnector[]>
	);

	// Get display info for OAuth connector type
	const getOAuthConnectorTypeInfo = (connectorType: string) => {
		// Check both OAUTH_CONNECTORS and COMPOSIO_CONNECTORS
		const oauthConnector =
			OAUTH_CONNECTORS.find((c) => c.connectorType === connectorType) ||
			COMPOSIO_CONNECTORS.find((c) => c.connectorType === connectorType);
		return {
			title:
				oauthConnector?.title ||
				connectorType
					.replace(/_/g, " ")
					.replace(/connector/gi, "")
					.trim(),
		};
	};

	// Filter OAuth connector types based on search query
	const filteredOAuthConnectorTypes = Object.entries(oauthConnectorsByType).filter(
		([connectorType]) => {
			if (!searchQuery) return true;
			const searchLower = searchQuery.toLowerCase();
			const { title } = getOAuthConnectorTypeInfo(connectorType);
			return (
				title.toLowerCase().includes(searchLower) ||
				connectorType.toLowerCase().includes(searchLower)
			);
		}
	);

	// Filter non-OAuth connectors based on search query
	const filteredNonOAuthConnectors = nonOauthConnectors.filter((connector) => {
		if (!searchQuery) return true;
		const searchLower = searchQuery.toLowerCase();
		return (
			connector.name.toLowerCase().includes(searchLower) ||
			connector.connector_type.toLowerCase().includes(searchLower)
		);
	});

	const hasActiveConnectors =
		filteredOAuthConnectorTypes.length > 0 || filteredNonOAuthConnectors.length > 0;

	return (
		<TabsContent value="active" className="m-0">
			{hasSources ? (
				<div className="space-y-6">
					{/* Active Connectors Section */}
					{hasActiveConnectors && (
						<div className="space-y-4">
							<div className="flex items-center gap-2">
								<h3 className="text-sm font-semibold text-muted-foreground">Active Connectors</h3>
							</div>
							<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
								{/* OAuth Connectors - Grouped by Type */}
								{filteredOAuthConnectorTypes.map(([connectorType, typeConnectors]) => {
									const { title } = getOAuthConnectorTypeInfo(connectorType);
									const isAnyIndexing = typeConnectors.some((c: SearchSourceConnector) =>
										indexingConnectorIds.has(c.id)
									);
									const documentCount = getDocumentCountForConnector(
										connectorType,
										documentTypeCounts
									);
									const accountCount = typeConnectors.length;

									const handleManageClick = () => {
										if (onViewAccountsList) {
											onViewAccountsList(connectorType, title);
										} else if (onManage && typeConnectors[0]) {
											onManage(typeConnectors[0]);
										}
									};

									return (
										<div
											key={`oauth-type-${connectorType}`}
											className={cn(
												"relative flex items-center gap-4 p-4 rounded-xl transition-all",
												isAnyIndexing
													? "bg-primary/5 border-0"
													: "bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10 border border-border"
											)}
										>
											<div
												className={cn(
													"flex h-12 w-12 items-center justify-center rounded-lg border shrink-0",
													isAnyIndexing
														? "bg-primary/10 border-primary/20"
														: "bg-slate-400/5 dark:bg-white/5 border-slate-400/5 dark:border-white/5"
												)}
											>
												{getConnectorIcon(connectorType, "size-6")}
											</div>
											<div className="flex-1 min-w-0">
												<p className="text-[14px] font-semibold leading-tight truncate">{title}</p>
												{isAnyIndexing ? (
													<p className="text-[11px] text-primary mt-1 flex items-center gap-1.5">
														<Spinner size="xs" />
														Syncing
													</p>
												) : (
													<p className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1.5">
														<span>{formatDocumentCount(documentCount)}</span>
														<span className="text-muted-foreground/50">•</span>
														<span>
															{accountCount} {accountCount === 1 ? "Account" : "Accounts"}
														</span>
													</p>
												)}
											</div>
											<Button
												variant="secondary"
												size="sm"
												className="h-8 text-[11px] px-3 rounded-lg font-medium bg-white text-slate-700 hover:bg-slate-50 border-0 shadow-xs dark:bg-secondary dark:text-secondary-foreground dark:hover:bg-secondary/80 shrink-0"
												onClick={handleManageClick}
											>
												Manage
											</Button>
										</div>
									);
								})}

								{/* Non-OAuth Connectors - Individual Cards */}
								{filteredNonOAuthConnectors.map((connector) => {
									const isIndexing = indexingConnectorIds.has(connector.id);
									const documentCount = getDocumentCountForConnector(
										connector.connector_type,
										documentTypeCounts
									);
									const isMCPConnector = connector.connector_type === "MCP_CONNECTOR";
									return (
										<div
											key={`connector-${connector.id}`}
											className={cn(
												"flex items-center gap-4 p-4 rounded-xl transition-all",
												isIndexing
													? "bg-primary/5 border-0"
													: "bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10 border border-border"
											)}
										>
											<div
												className={cn(
													"flex h-12 w-12 items-center justify-center rounded-lg border shrink-0",
													isIndexing
														? "bg-primary/10 border-primary/20"
														: "bg-slate-400/5 dark:bg-white/5 border-slate-400/5 dark:border-white/5"
												)}
											>
												{getConnectorIcon(connector.connector_type, "size-6")}
											</div>
											<div className="flex-1 min-w-0">
												<div className="flex items-center gap-2">
													<p className="text-[14px] font-semibold leading-tight truncate">
														{getConnectorDisplayName(connector.name)}
													</p>
												</div>
												{isIndexing ? (
													<p className="text-[11px] text-primary mt-1 flex items-center gap-1.5">
														<Spinner size="xs" />
														Syncing
													</p>
												) : !isMCPConnector ? (
													<p className="text-[10px] text-muted-foreground mt-1">
														{formatDocumentCount(documentCount)}
													</p>
												) : null}
											</div>
											<Button
												variant="secondary"
												size="sm"
												className="h-8 text-[11px] px-3 rounded-lg font-medium bg-white text-slate-700 hover:bg-slate-50 border-0 shadow-xs dark:bg-secondary dark:text-secondary-foreground dark:hover:bg-secondary/80 shrink-0"
												onClick={onManage ? () => onManage(connector) : undefined}
											>
												Manage
											</Button>
										</div>
									);
								})}
							</div>
						</div>
					)}

					{/* Standalone Documents Section */}
					{standaloneDocuments.length > 0 && (
						<div className="space-y-4">
							<div className="flex items-center justify-between">
								<h3 className="text-sm font-semibold text-muted-foreground">Documents</h3>
								<Button
									variant="ghost"
									size="sm"
									onClick={handleViewAllDocuments}
									className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1.5"
								>
									View all documents
									<ArrowRight className="size-3" />
								</Button>
							</div>
							<div className="flex flex-wrap items-center gap-2">
								{standaloneDocuments.map((doc) => (
									<div
										key={doc.type}
										className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10 transition-all"
									>
										<div className="flex items-center justify-center">
											{getConnectorIcon(doc.type, "size-3.5")}
										</div>
										<span className="text-[12px] font-medium">{doc.label}</span>
										<span className="text-[11px] text-muted-foreground">
											{formatDocumentCount(doc.count)}
										</span>
									</div>
								))}
							</div>
						</div>
					)}
				</div>
			) : (
				<div className="flex flex-col items-center justify-center py-20 text-center">
					<div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted mb-4">
						<Cable className="size-8 text-muted-foreground" />
					</div>
					<h4 className="text-lg font-semibold">No active sources</h4>
					<p className="text-sm text-muted-foreground mt-1 max-w-[280px]">
						Connect your first service to start searching across all your data.
					</p>
				</div>
			)}
		</TabsContent>
	);
};
