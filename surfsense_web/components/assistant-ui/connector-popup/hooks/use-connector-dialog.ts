import { useAtomValue } from "jotai";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { createConnectorMutationAtom, deleteConnectorMutationAtom, indexConnectorMutationAtom, updateConnectorMutationAtom } from "@/atoms/connectors/connector-mutation.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { authenticatedFetch } from "@/lib/auth-utils";
import { queryClient } from "@/lib/query-client/client";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { format } from "date-fns";
import { EnumConnectorName } from "@/contracts/enums/connector";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { searchSourceConnector } from "@/contracts/types/connector.types";
import { OAUTH_CONNECTORS, OTHER_CONNECTORS } from "../constants/connector-constants";
import type { IndexingConfigState } from "../constants/connector-constants";
import {
	parseConnectorPopupQueryParams,
	parseOAuthAuthResponse,
	validateIndexingConfigState,
	frequencyMinutesSchema,
	dateRangeSchema,
} from "../constants/connector-popup.schemas";

export const useConnectorDialog = () => {
	const router = useRouter();
	const searchParams = useSearchParams();
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { data: allConnectors, refetch: refetchAllConnectors } = useAtomValue(connectorsAtom);
	const { mutateAsync: indexConnector } = useAtomValue(indexConnectorMutationAtom);
	const { mutateAsync: updateConnector } = useAtomValue(updateConnectorMutationAtom);
	const { mutateAsync: deleteConnector } = useAtomValue(deleteConnectorMutationAtom);
	const { mutateAsync: createConnector } = useAtomValue(createConnectorMutationAtom);

	const [isOpen, setIsOpen] = useState(false);
	const [activeTab, setActiveTab] = useState("all");
	const [connectingId, setConnectingId] = useState<string | null>(null);
	const [isScrolled, setIsScrolled] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	const [indexingConfig, setIndexingConfig] = useState<IndexingConfigState | null>(null);
	const [indexingConnector, setIndexingConnector] = useState<SearchSourceConnector | null>(null);
	const [indexingConnectorConfig, setIndexingConnectorConfig] = useState<Record<string, unknown> | null>(null);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [isStartingIndexing, setIsStartingIndexing] = useState(false);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
	
	// Edit mode state
	const [editingConnector, setEditingConnector] = useState<SearchSourceConnector | null>(null);
	const [isSaving, setIsSaving] = useState(false);
	const [isDisconnecting, setIsDisconnecting] = useState(false);
	const [connectorConfig, setConnectorConfig] = useState<Record<string, unknown> | null>(null);
	const [connectorName, setConnectorName] = useState<string | null>(null);
	
	// Connect mode state (for non-OAuth connectors)
	const [connectingConnectorType, setConnectingConnectorType] = useState<string | null>(null);
	const [isCreatingConnector, setIsCreatingConnector] = useState(false);
	const isCreatingConnectorRef = useRef(false);

	// Helper function to get frequency label
	const getFrequencyLabel = useCallback((minutes: string): string => {
		switch (minutes) {
			case "15": return "15 minutes";
			case "60": return "hour";
			case "360": return "6 hours";
			case "720": return "12 hours";
			case "1440": return "day";
			case "10080": return "week";
			default: return `${minutes} minutes`;
		}
	}, []);

	// Synchronize state with URL query params
	useEffect(() => {
		try {
			const params = parseConnectorPopupQueryParams(searchParams);
			
			if (params.modal === "connectors") {
				setIsOpen(true);
				
				if (params.tab === "active" || params.tab === "all") {
					setActiveTab(params.tab);
				}
				
				// Clear indexing config if view is not "configure" anymore
				if (params.view !== "configure" && indexingConfig) {
					setIndexingConfig(null);
				}
				
				// Clear editing connector if view is not "edit" anymore
				if (params.view !== "edit" && editingConnector) {
					setEditingConnector(null);
					setConnectorName(null);
				}
				
				// Clear connecting connector type if view is not "connect" anymore
				if (params.view !== "connect" && connectingConnectorType) {
					setConnectingConnectorType(null);
				}
				
				// Handle connect view
				if (params.view === "connect" && params.connectorType && !connectingConnectorType) {
					setConnectingConnectorType(params.connectorType);
				}
				
				// Handle YouTube view
				if (params.view === "youtube") {
					// YouTube view is active - no additional state needed
				}
				
				if (params.view === "configure" && params.connector && !indexingConfig) {
					const oauthConnector = OAUTH_CONNECTORS.find(c => c.id === params.connector);
					if (oauthConnector && allConnectors) {
						const existingConnector = allConnectors.find(
							(c: SearchSourceConnector) => c.connector_type === oauthConnector.connectorType
						);
						if (existingConnector) {
							// Validate connector data before setting state
							const connectorValidation = searchSourceConnector.safeParse(existingConnector);
							if (connectorValidation.success) {
								const config = validateIndexingConfigState({
									connectorType: oauthConnector.connectorType,
									connectorId: existingConnector.id,
									connectorTitle: oauthConnector.title,
								});
								setIndexingConfig(config);
								setIndexingConnector(existingConnector);
								setIndexingConnectorConfig(existingConnector.config);
							}
						}
					}
				}
				
				// Handle edit view
				if (params.view === "edit" && params.connectorId && allConnectors && !editingConnector) {
					const connectorId = parseInt(params.connectorId, 10);
					const connector = allConnectors.find((c: SearchSourceConnector) => c.id === connectorId);
					if (connector) {
						const connectorValidation = searchSourceConnector.safeParse(connector);
						if (connectorValidation.success) {
							setEditingConnector(connector);
							setConnectorConfig(connector.config);
							// Load existing periodic sync settings (disabled for Google Drive)
							setPeriodicEnabled(connector.connector_type === "GOOGLE_DRIVE_CONNECTOR" ? false : connector.periodic_indexing_enabled);
							setFrequencyMinutes(
								connector.indexing_frequency_minutes?.toString() || "1440"
							);
							// Reset dates - user can set new ones for re-indexing
							setStartDate(undefined);
							setEndDate(undefined);
						}
					}
				}
			} else {
				setIsOpen(false);
				// Clear indexing config when modal is closed
				if (indexingConfig) {
					setIndexingConfig(null);
					setIndexingConnector(null);
					setIndexingConnectorConfig(null);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
					setIsScrolled(false);
					setSearchQuery("");
				}
				// Clear editing connector when modal is closed
				if (editingConnector) {
					setEditingConnector(null);
					setConnectorName(null);
					setConnectorConfig(null);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
					setIsScrolled(false);
					setSearchQuery("");
				}
				// Clear connecting connector type when modal is closed
				if (connectingConnectorType) {
					setConnectingConnectorType(null);
				}
				// Clear YouTube view when modal is closed (handled by view param check)
			}
		} catch (error) {
			// Invalid query params - log but don't crash
			console.warn("Invalid connector popup query params:", error);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [searchParams, allConnectors, editingConnector, indexingConfig, connectingConnectorType]);

	// Detect OAuth success and transition to config view
	useEffect(() => {
		try {
			const params = parseConnectorPopupQueryParams(searchParams);
			
			if (params.success === "true" && params.connector && searchSpaceId && params.modal === "connectors") {
				const oauthConnector = OAUTH_CONNECTORS.find(c => c.id === params.connector);
				if (oauthConnector) {
					refetchAllConnectors().then((result) => {
						if (!result.data) return;
						
						const newConnector = result.data.find(
							(c: SearchSourceConnector) => c.connector_type === oauthConnector.connectorType
						);
						if (newConnector) {
							// Validate connector data before setting state
							const connectorValidation = searchSourceConnector.safeParse(newConnector);
							if (connectorValidation.success) {
								const config = validateIndexingConfigState({
									connectorType: oauthConnector.connectorType,
									connectorId: newConnector.id,
									connectorTitle: oauthConnector.title,
								});
								setIndexingConfig(config);
								setIndexingConnector(newConnector);
								setIndexingConnectorConfig(newConnector.config);
								setIsOpen(true);
								const url = new URL(window.location.href);
								url.searchParams.delete("success");
								url.searchParams.set("view", "configure");
								window.history.replaceState({}, "", url.toString());
							} else {
								console.warn("Invalid connector data after OAuth:", connectorValidation.error);
								toast.error("Failed to validate connector data");
							}
						}
					});
				}
			}
		} catch (error) {
			// Invalid query params - log but don't crash
			console.warn("Invalid connector popup query params in OAuth success handler:", error);
		}
	}, [searchParams, searchSpaceId, refetchAllConnectors]);

	// Handle OAuth connection
	const handleConnectOAuth = useCallback(
		async (connector: (typeof OAUTH_CONNECTORS)[number]) => {
			if (!searchSpaceId || !connector.authEndpoint) return;

			// Set connecting state immediately to disable button and show spinner
			setConnectingId(connector.id);

			try {
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}${connector.authEndpoint}?space_id=${searchSpaceId}`,
					{ method: "GET" }
				);

				if (!response.ok) {
					throw new Error(`Failed to initiate ${connector.title} OAuth`);
				}

				const data = await response.json();
				
				// Validate OAuth response with Zod
				const validatedData = parseOAuthAuthResponse(data);
				
				// Don't clear connectingId here - let the redirect happen with button still disabled
				// The component will unmount on redirect anyway
				window.location.href = validatedData.auth_url;
			} catch (error) {
				console.error(`Error connecting to ${connector.title}:`, error);
				if (error instanceof Error && error.message.includes("Invalid auth URL")) {
					toast.error(`Invalid response from ${connector.title} OAuth endpoint`);
				} else {
					toast.error(`Failed to connect to ${connector.title}`);
				}
				// Only clear connectingId on error so user can retry
				setConnectingId(null);
			}
		},
		[searchSpaceId]
	);

	// Handle creating YouTube crawler (not a connector, shows view in popup)
	const handleCreateYouTubeCrawler = useCallback(() => {
		if (!searchSpaceId) return;
		
		// Update URL to show YouTube view
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("view", "youtube");
		window.history.pushState({ modal: true }, "", url.toString());
	}, [searchSpaceId]);

	// Handle creating webcrawler connector
	const handleCreateWebcrawler = useCallback(async () => {
		if (!searchSpaceId) return;

		setConnectingId("webcrawler-connector");
		try {
			await createConnector({
				data: {
					name: "Web Pages",
					connector_type: EnumConnectorName.WEBCRAWLER_CONNECTOR,
					config: {},
					is_indexable: true,
					last_indexed_at: null,
					periodic_indexing_enabled: false,
					indexing_frequency_minutes: null,
					next_scheduled_at: null,
				},
				queryParams: {
					search_space_id: searchSpaceId,
				},
			});

			// Refetch connectors to get the new one
			const result = await refetchAllConnectors();
			if (result.data) {
				const connector = result.data.find(
					(c: SearchSourceConnector) => c.connector_type === EnumConnectorName.WEBCRAWLER_CONNECTOR
				);
				if (connector) {
					const connectorValidation = searchSourceConnector.safeParse(connector);
					if (connectorValidation.success) {
						const config = validateIndexingConfigState({
							connectorType: EnumConnectorName.WEBCRAWLER_CONNECTOR,
							connectorId: connector.id,
							connectorTitle: "Web Pages",
						});
						setIndexingConfig(config);
						setIndexingConnector(connector);
						setIndexingConnectorConfig(connector.config || {});
						setIsOpen(true);
						const url = new URL(window.location.href);
						url.searchParams.set("modal", "connectors");
						url.searchParams.set("view", "configure");
						window.history.pushState({ modal: true }, "", url.toString());
					}
				}
			}
		} catch (error) {
			console.error("Error creating webcrawler connector:", error);
			toast.error("Failed to create web crawler connector");
		} finally {
			setConnectingId(null);
		}
	}, [searchSpaceId, createConnector, refetchAllConnectors]);

	// Handle connecting non-OAuth connectors (like Tavily API)
	const handleConnectNonOAuth = useCallback((connectorType: string) => {
		if (!searchSpaceId) return;
		
		// Set connecting state
		setConnectingConnectorType(connectorType);
		
		// Update URL to show connect view
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("view", "connect");
		url.searchParams.set("connectorType", connectorType);
		window.history.pushState({ modal: true }, "", url.toString());
	}, [searchSpaceId]);

	// Handle submitting connect form
	const handleSubmitConnectForm = useCallback(async (
		formData: {
			name: string;
			connector_type: string;
			config: Record<string, unknown>;
			is_indexable: boolean;
			last_indexed_at: null;
			periodic_indexing_enabled: boolean;
			indexing_frequency_minutes: number | null;
			next_scheduled_at: null;
			startDate?: Date;
			endDate?: Date;
			periodicEnabled?: boolean;
			frequencyMinutes?: string;
		}
	) => {
		if (!searchSpaceId || !connectingConnectorType) return;
		
		// Prevent multiple submissions using ref for immediate check
		if (isCreatingConnectorRef.current) return;
		isCreatingConnectorRef.current = true;

		setIsCreatingConnector(true);
		try {
			// Extract UI-only fields before sending to backend
			const { startDate, endDate, periodicEnabled, frequencyMinutes, ...connectorData } = formData;
			
			// Create connector - ensure types match the schema
			const newConnector = await createConnector({
				data: {
					...connectorData,
					connector_type: connectorData.connector_type as EnumConnectorName,
					next_scheduled_at: connectorData.next_scheduled_at as string | null,
				},
				queryParams: {
					search_space_id: searchSpaceId,
				},
			});

			// Refetch connectors to get the new one
			const result = await refetchAllConnectors();
			if (result.data) {
				const connector = result.data.find(
					(c: SearchSourceConnector) => c.id === newConnector.id
				);
				if (connector) {
					// Validate connector data
					const connectorValidation = searchSourceConnector.safeParse(connector);
					if (connectorValidation.success) {
						// Store connectingConnectorType before clearing it
						const currentConnectorType = connectingConnectorType;
						
						// Find connector title from constants
						const connectorInfo = OTHER_CONNECTORS.find(
							c => c.connectorType === currentConnectorType
						);
						const connectorTitle = connectorInfo?.title || connector.name;
						
						// Set up indexing config
						const config = validateIndexingConfigState({
							connectorType: currentConnectorType as EnumConnectorName,
							connectorId: connector.id,
							connectorTitle,
						});
						
						// Clear connecting state to allow view transition
						setConnectingConnectorType(null);
						
						// Set indexing config state
						setIndexingConfig(config);
						setIndexingConnector(connector);
						setIndexingConnectorConfig(connector.config || {});
						
						// Pre-populate indexing configuration with values from form if provided
						if (formData.startDate !== undefined) {
							setStartDate(formData.startDate);
						}
						if (formData.endDate !== undefined) {
							setEndDate(formData.endDate);
						}
						if (formData.periodicEnabled !== undefined) {
							setPeriodicEnabled(formData.periodicEnabled);
						}
						if (formData.frequencyMinutes !== undefined) {
							setFrequencyMinutes(formData.frequencyMinutes);
						}
						
						// Auto-start indexing for non-OAuth reindexable connectors
						// This only applies to non-OAuth reindexable connectors (e.g., Elasticsearch, Linear)
						// Non-reindexable connectors (e.g., Tavily) have is_indexable: false, so they won't trigger this
						// Backend will use default date ranges (365 days ago to today) if dates are not provided
						if (connector.is_indexable) {
							// Get indexing configuration from form (or use defaults)
							const startDateForIndexing = formData.startDate;
							const endDateForIndexing = formData.endDate;
							const periodicEnabledForIndexing = formData.periodicEnabled || false;
							const frequencyMinutesForIndexing = formData.frequencyMinutes || "1440";
							
							// Update connector with periodic sync settings if enabled
							if (periodicEnabledForIndexing) {
								const frequency = parseInt(frequencyMinutesForIndexing, 10);
								await updateConnector({
									id: connector.id,
									data: {
										periodic_indexing_enabled: true,
										indexing_frequency_minutes: frequency,
									},
								});
							}
							
							// Start indexing (backend will use defaults if dates are undefined)
							const startDateStr = startDateForIndexing ? format(startDateForIndexing, "yyyy-MM-dd") : undefined;
							const endDateStr = endDateForIndexing ? format(endDateForIndexing, "yyyy-MM-dd") : undefined;
							
							await indexConnector({
								connector_id: connector.id,
								queryParams: {
									search_space_id: searchSpaceId,
									start_date: startDateStr,
									end_date: endDateStr,
								},
							});
							
							toast.success(`${connectorTitle} connected and indexing started!`, {
								description: periodicEnabledForIndexing 
									? `Periodic sync enabled every ${getFrequencyLabel(frequencyMinutesForIndexing)}.`
									: "You can continue working while we sync your data.",
							});
							
							// Close modal and return to main view
							const url = new URL(window.location.href);
							url.searchParams.delete("modal");
							url.searchParams.delete("tab");
							url.searchParams.delete("view");
							url.searchParams.delete("connectorType");
							router.replace(url.pathname + url.search, { scroll: false });
							
							// Clear indexing config state since we're not showing the view
							setIndexingConfig(null);
							setIndexingConnector(null);
							setIndexingConnectorConfig(null);
							
							// Invalidate queries to refresh data
							queryClient.invalidateQueries({
								queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
							});
							
							// Refresh connectors list
							await refetchAllConnectors();
						} else {
							// Non-indexable connector - just show success message
							toast.success(`${connectorTitle} connected successfully!`);
							
							// Close modal and return to main view
							const url = new URL(window.location.href);
							url.searchParams.delete("modal");
							url.searchParams.delete("tab");
							url.searchParams.delete("view");
							url.searchParams.delete("connectorType");
							router.replace(url.pathname + url.search, { scroll: false });
						}
					}
				}
			}
		} catch (error) {
			console.error("Error creating connector:", error);
			toast.error(error instanceof Error ? error.message : "Failed to create connector");
		} finally {
			isCreatingConnectorRef.current = false;
			setIsCreatingConnector(false);
			// Don't clear connectingConnectorType here - it's cleared above when transitioning to config view
		}
		}, [connectingConnectorType, searchSpaceId, createConnector, refetchAllConnectors, updateConnector, indexConnector, router, getFrequencyLabel]);

	// Handle going back from connect view
	const handleBackFromConnect = useCallback(() => {
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("tab", "all");
		url.searchParams.delete("view");
		url.searchParams.delete("connectorType");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router]);

	// Handle going back from YouTube view
	const handleBackFromYouTube = useCallback(() => {
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("tab", "all");
		url.searchParams.delete("view");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router]);

	// Handle starting indexing
	const handleStartIndexing = useCallback(async (refreshConnectors: () => void) => {
		if (!indexingConfig || !searchSpaceId) return;

		// Validate date range (skip for Google Drive and Webcrawler)
		if (indexingConfig.connectorType !== "GOOGLE_DRIVE_CONNECTOR" && indexingConfig.connectorType !== "WEBCRAWLER_CONNECTOR") {
			const dateRangeValidation = dateRangeSchema.safeParse({ startDate, endDate });
			if (!dateRangeValidation.success) {
				const firstIssueMsg =
					dateRangeValidation.error.issues && dateRangeValidation.error.issues.length > 0
						? dateRangeValidation.error.issues[0].message
						: "Invalid date range";
				toast.error(firstIssueMsg);
				return;
			}
		}

		// Validate frequency minutes if periodic is enabled
		if (periodicEnabled) {
			const frequencyValidation = frequencyMinutesSchema.safeParse(frequencyMinutes);
			if (!frequencyValidation.success) {
				toast.error("Invalid frequency value");
				return;
			}
		}

		setIsStartingIndexing(true);
		try {
			const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
			const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

			// Update connector with periodic sync settings and config changes
			// Note: Periodic sync is disabled for Google Drive connectors
			if (periodicEnabled || indexingConnectorConfig) {
				const frequency = periodicEnabled ? parseInt(frequencyMinutes, 10) : undefined;
				await updateConnector({
					id: indexingConfig.connectorId,
					data: {
						...(periodicEnabled && indexingConfig.connectorType !== "GOOGLE_DRIVE_CONNECTOR" && {
							periodic_indexing_enabled: true,
							indexing_frequency_minutes: frequency,
						}),
						...(indexingConfig.connectorType === "GOOGLE_DRIVE_CONNECTOR" && {
							periodic_indexing_enabled: false,
							indexing_frequency_minutes: null,
						}),
						...(indexingConnectorConfig && {
							config: indexingConnectorConfig,
						}),
					},
				});
			}

			// Handle Google Drive folder selection
			if (indexingConfig.connectorType === "GOOGLE_DRIVE_CONNECTOR" && indexingConnectorConfig) {
				const selectedFolders = indexingConnectorConfig.selected_folders as Array<{ id: string; name: string }> | undefined;
				const selectedFiles = indexingConnectorConfig.selected_files as Array<{ id: string; name: string }> | undefined;
				if ((selectedFolders && selectedFolders.length > 0) || (selectedFiles && selectedFiles.length > 0)) {
					// Index with folder/file selection
					await indexConnector({
						connector_id: indexingConfig.connectorId,
						queryParams: {
							search_space_id: searchSpaceId,
						},
						body: {
							folders: selectedFolders || [],
							files: selectedFiles || [],
						},
					});
				} else {
					// Google Drive requires folder selection - show error if none selected
					toast.error("Please select at least one folder to index");
					setIsStartingIndexing(false);
					return;
				}
			} else if (indexingConfig.connectorType === "WEBCRAWLER_CONNECTOR") {
				// Webcrawler doesn't use date ranges, just uses config (API key and URLs)
				await indexConnector({
					connector_id: indexingConfig.connectorId,
					queryParams: {
						search_space_id: searchSpaceId,
					},
				});
			} else {
				await indexConnector({
					connector_id: indexingConfig.connectorId,
					queryParams: {
						search_space_id: searchSpaceId,
						start_date: startDateStr,
						end_date: endDateStr,
					},
				});
			}

			toast.success(`${indexingConfig.connectorTitle} indexing started`, {
				description: periodicEnabled 
					? `Periodic sync enabled every ${getFrequencyLabel(frequencyMinutes)}.`
					: "You can continue working while we sync your data.",
			});

			// Update URL - the effect will handle closing the modal and clearing state
			const url = new URL(window.location.href);
			url.searchParams.delete("modal");
			url.searchParams.delete("tab");
			url.searchParams.delete("success");
			url.searchParams.delete("connector");
			url.searchParams.delete("view");
			router.replace(url.pathname + url.search, { scroll: false });
			
			refreshConnectors();
			queryClient.invalidateQueries({
				queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
			});
		} catch (error) {
			console.error("Error starting indexing:", error);
			toast.error("Failed to start indexing");
		} finally {
			setIsStartingIndexing(false);
		}
	}, [indexingConfig, searchSpaceId, startDate, endDate, indexConnector, updateConnector, periodicEnabled, frequencyMinutes, getFrequencyLabel, router, indexingConnectorConfig]);

	// Handle skipping indexing
	const handleSkipIndexing = useCallback(() => {
		// Update URL - the effect will handle closing the modal and clearing state
		const url = new URL(window.location.href);
		url.searchParams.delete("modal");
		url.searchParams.delete("tab");
		url.searchParams.delete("success");
		url.searchParams.delete("connector");
		url.searchParams.delete("view");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router]);

	// Handle starting edit mode
	const handleStartEdit = useCallback((connector: SearchSourceConnector) => {
		if (!searchSpaceId) return;
		
		// All connector types should be handled in the popup edit view
		// Validate connector data
		const connectorValidation = searchSourceConnector.safeParse(connector);
		if (!connectorValidation.success) {
			toast.error("Invalid connector data");
			return;
		}
		
		setEditingConnector(connector);
		setConnectorName(connector.name);
		// Load existing periodic sync settings (disabled for Google Drive)
		setPeriodicEnabled(connector.connector_type === "GOOGLE_DRIVE_CONNECTOR" ? false : connector.periodic_indexing_enabled);
		setFrequencyMinutes(connector.indexing_frequency_minutes?.toString() || "1440");
		// Reset dates - user can set new ones for re-indexing
		setStartDate(undefined);
		setEndDate(undefined);
		
		// Update URL
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("view", "edit");
		url.searchParams.set("connectorId", connector.id.toString());
		window.history.pushState({ modal: true }, "", url.toString());
	}, [searchSpaceId]);

	// Handle saving connector changes
	const handleSaveConnector = useCallback(async (refreshConnectors: () => void) => {
		if (!editingConnector || !searchSpaceId) return;

		// Validate date range (skip for Google Drive which uses folder selection, Webcrawler which uses config, and non-indexable connectors)
		if (editingConnector.is_indexable && editingConnector.connector_type !== "GOOGLE_DRIVE_CONNECTOR" && editingConnector.connector_type !== "WEBCRAWLER_CONNECTOR") {
			const dateRangeValidation = dateRangeSchema.safeParse({ startDate, endDate });
			if (!dateRangeValidation.success) {
				toast.error(dateRangeValidation.error.issues[0]?.message || "Invalid date range");
				return;
			}
		}

		// Prevent periodic indexing for non-indexable connectors
		if (periodicEnabled && !editingConnector.is_indexable) {
			toast.error("Periodic indexing is not available for this connector type");
			return;
		}

		// Validate frequency minutes if periodic is enabled (only for indexable connectors)
		if (periodicEnabled && editingConnector.is_indexable) {
			const frequencyValidation = frequencyMinutesSchema.safeParse(frequencyMinutes);
			if (!frequencyValidation.success) {
				toast.error("Invalid frequency value");
				return;
			}
		}

		setIsSaving(true);
		try {
			const startDateStr = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
			const endDateStr = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

			// Update connector with periodic sync settings, config changes, and name
			// Note: Periodic sync is disabled for Google Drive connectors
			const frequency = periodicEnabled ? parseInt(frequencyMinutes, 10) : null;
			await updateConnector({
				id: editingConnector.id,
				data: {
					name: connectorName || editingConnector.name,
					periodic_indexing_enabled: editingConnector.connector_type === "GOOGLE_DRIVE_CONNECTOR" ? false : periodicEnabled,
					indexing_frequency_minutes: editingConnector.connector_type === "GOOGLE_DRIVE_CONNECTOR" ? null : frequency,
					config: connectorConfig || editingConnector.config,
				},
			});

			// Re-index based on connector type (only for indexable connectors)
			let indexingDescription = "Settings saved.";
			if (!editingConnector.is_indexable) {
				// Non-indexable connectors (like Tavily API) don't need re-indexing
				indexingDescription = "Settings saved.";
			} else if (editingConnector.connector_type === "GOOGLE_DRIVE_CONNECTOR") {
				// Google Drive uses folder selection from config, not date ranges
				const selectedFolders = (connectorConfig || editingConnector.config)?.selected_folders as Array<{ id: string; name: string }> | undefined;
				const selectedFiles = (connectorConfig || editingConnector.config)?.selected_files as Array<{ id: string; name: string }> | undefined;
				if ((selectedFolders && selectedFolders.length > 0) || (selectedFiles && selectedFiles.length > 0)) {
					await indexConnector({
						connector_id: editingConnector.id,
						queryParams: {
							search_space_id: searchSpaceId,
						},
						body: {
							folders: selectedFolders || [],
							files: selectedFiles || [],
						},
					});
					const totalItems = (selectedFolders?.length || 0) + (selectedFiles?.length || 0);
					indexingDescription = `Re-indexing started for ${totalItems} item(s).`;
				}
			} else if (editingConnector.connector_type === "WEBCRAWLER_CONNECTOR") {
				// Webcrawler uses config (API key and URLs), not date ranges
				await indexConnector({
					connector_id: editingConnector.id,
					queryParams: {
						search_space_id: searchSpaceId,
					},
				});
				indexingDescription = "Re-indexing started with updated configuration.";
			} else if (startDateStr || endDateStr) {
				// Other connectors use date ranges
				await indexConnector({
					connector_id: editingConnector.id,
					queryParams: {
						search_space_id: searchSpaceId,
						start_date: startDateStr,
						end_date: endDateStr,
					},
				});
				indexingDescription = "Re-indexing started with new date range.";
			}

			toast.success(`${editingConnector.name} updated successfully`, {
				description: periodicEnabled 
					? `Periodic sync ${frequency ? `enabled every ${getFrequencyLabel(frequencyMinutes)}` : "enabled"}. ${indexingDescription}`
					: indexingDescription,
			});

			// Update URL - the effect will handle closing the modal and clearing state
			const url = new URL(window.location.href);
			url.searchParams.delete("modal");
			url.searchParams.delete("tab");
			url.searchParams.delete("view");
			url.searchParams.delete("connectorId");
			router.replace(url.pathname + url.search, { scroll: false });
			
			refreshConnectors();
			queryClient.invalidateQueries({
				queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
			});
		} catch (error) {
			console.error("Error saving connector:", error);
			toast.error("Failed to save connector changes");
		} finally {
			setIsSaving(false);
		}
	}, [editingConnector, searchSpaceId, startDate, endDate, indexConnector, updateConnector, periodicEnabled, frequencyMinutes, getFrequencyLabel, router, connectorConfig, connectorName]);

	// Handle disconnecting connector
	const handleDisconnectConnector = useCallback(async (refreshConnectors: () => void) => {
		if (!editingConnector || !searchSpaceId) return;

		setIsDisconnecting(true);
		try {
			await deleteConnector({
				id: editingConnector.id,
			});

			toast.success(`${editingConnector.name} disconnected successfully`);

			// Update URL - the effect will handle closing the modal and clearing state
			const url = new URL(window.location.href);
			url.searchParams.delete("modal");
			url.searchParams.delete("tab");
			url.searchParams.delete("view");
			url.searchParams.delete("connectorId");
			router.replace(url.pathname + url.search, { scroll: false });
			
			refreshConnectors();
			queryClient.invalidateQueries({
				queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
			});
		} catch (error) {
			console.error("Error disconnecting connector:", error);
			toast.error("Failed to disconnect connector");
		} finally {
			setIsDisconnecting(false);
		}
	}, [editingConnector, searchSpaceId, deleteConnector, router]);

	// Handle quick index (index without date picker, uses backend defaults)
	const handleQuickIndexConnector = useCallback(async (connectorId: number) => {
		if (!searchSpaceId) return;
		
		try {
			await indexConnector({
				connector_id: connectorId,
				queryParams: {
					search_space_id: searchSpaceId,
				},
			});
			toast.success("Indexing started", {
				description: "You can continue working while we sync your data.",
			});
			
			// Invalidate queries to refresh data
			queryClient.invalidateQueries({
				queryKey: cacheKeys.logs.summary(Number(searchSpaceId)),
			});
		} catch (error) {
			console.error("Error indexing connector content:", error);
			toast.error(error instanceof Error ? error.message : "Failed to start indexing");
		}
	}, [searchSpaceId, indexConnector]);

	// Handle going back from edit view
	const handleBackFromEdit = useCallback(() => {
		const url = new URL(window.location.href);
		url.searchParams.set("modal", "connectors");
		url.searchParams.set("tab", "all");
		url.searchParams.delete("view");
		url.searchParams.delete("connectorId");
		router.replace(url.pathname + url.search, { scroll: false });
	}, [router]);

	// Handle dialog open/close
	const handleOpenChange = useCallback(
		(open: boolean) => {
			setIsOpen(open);

			if (open) {
				const url = new URL(window.location.href);
				url.searchParams.set("modal", "connectors");
				url.searchParams.set("tab", activeTab);
				window.history.pushState({ modal: true }, "", url.toString());
			} else {
				const url = new URL(window.location.href);
				url.searchParams.delete("modal");
				url.searchParams.delete("tab");
				url.searchParams.delete("success");
				url.searchParams.delete("connector");
				url.searchParams.delete("view");
				window.history.pushState({ modal: false }, "", url.toString());
				setIsScrolled(false);
				setSearchQuery("");
				if (!isStartingIndexing && !isSaving && !isDisconnecting && !isCreatingConnector) {
					setIndexingConfig(null);
					setIndexingConnector(null);
					setIndexingConnectorConfig(null);
					setEditingConnector(null);
					setConnectorName(null);
					setConnectorConfig(null);
					setConnectingConnectorType(null);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
				}
			}
		},
		[activeTab, isStartingIndexing, isDisconnecting, isSaving, isCreatingConnector]
	);

	// Handle tab change
	const handleTabChange = useCallback(
		(value: string) => {
			setActiveTab(value);
			const url = new URL(window.location.href);
			url.searchParams.set("tab", value);
			window.history.replaceState({ modal: true }, "", url.toString());
		},
		[]
	);

	// Handle scroll
	const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
		setIsScrolled(e.currentTarget.scrollTop > 0);
	}, []);

		return {
		// State
		isOpen,
		activeTab,
		connectingId,
		isScrolled,
		searchQuery,
		indexingConfig,
		indexingConnector,
		indexingConnectorConfig,
		editingConnector,
		connectingConnectorType,
		isCreatingConnector,
		startDate,
		endDate,
		isStartingIndexing,
		isSaving,
		isDisconnecting,
		periodicEnabled,
		frequencyMinutes,
		searchSpaceId,
		allConnectors,
		
		// Setters
		setSearchQuery,
		setStartDate,
		setEndDate,
		setPeriodicEnabled,
		setFrequencyMinutes,
		setConnectorName,
		
		// Handlers
		handleOpenChange,
		handleTabChange,
		handleScroll,
		handleConnectOAuth,
		handleConnectNonOAuth,
		handleCreateWebcrawler,
		handleCreateYouTubeCrawler,
		handleSubmitConnectForm,
		handleStartIndexing,
		handleSkipIndexing,
		handleStartEdit,
		handleSaveConnector,
		handleDisconnectConnector,
		handleBackFromEdit,
		handleBackFromConnect,
		handleBackFromYouTube,
		handleQuickIndexConnector,
		connectorConfig,
		setConnectorConfig,
		setIndexingConnectorConfig,
	};
};

