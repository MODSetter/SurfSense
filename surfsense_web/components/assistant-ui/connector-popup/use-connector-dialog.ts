import { useAtomValue } from "jotai";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { indexConnectorMutationAtom, updateConnectorMutationAtom } from "@/atoms/connectors/connector-mutation.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { authenticatedFetch } from "@/lib/auth-utils";
import { queryClient } from "@/lib/query-client/client";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { format } from "date-fns";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { searchSourceConnector } from "@/contracts/types/connector.types";
import { OAUTH_CONNECTORS } from "./connector-constants";
import type { IndexingConfigState } from "./connector-constants";
import {
	parseConnectorPopupQueryParams,
	parseOAuthAuthResponse,
	validateIndexingConfigState,
	frequencyMinutesSchema,
	dateRangeSchema,
} from "./connector-popup.schemas";

export const useConnectorDialog = () => {
	const router = useRouter();
	const searchParams = useSearchParams();
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { data: allConnectors, refetch: refetchAllConnectors } = useAtomValue(connectorsAtom);
	const { mutateAsync: indexConnector } = useAtomValue(indexConnectorMutationAtom);
	const { mutateAsync: updateConnector } = useAtomValue(updateConnectorMutationAtom);

	const [isOpen, setIsOpen] = useState(false);
	const [activeTab, setActiveTab] = useState("all");
	const [connectingId, setConnectingId] = useState<string | null>(null);
	const [isScrolled, setIsScrolled] = useState(false);
	const [searchQuery, setSearchQuery] = useState("");
	const [indexingConfig, setIndexingConfig] = useState<IndexingConfigState | null>(null);
	const [startDate, setStartDate] = useState<Date | undefined>(undefined);
	const [endDate, setEndDate] = useState<Date | undefined>(undefined);
	const [isStartingIndexing, setIsStartingIndexing] = useState(false);
	const [periodicEnabled, setPeriodicEnabled] = useState(false);
	const [frequencyMinutes, setFrequencyMinutes] = useState("1440");

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
							}
						}
					}
				}
			} else {
				setIsOpen(false);
				// Clear indexing config when modal is closed
				if (indexingConfig) {
					setIndexingConfig(null);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
					setIsScrolled(false);
					setSearchQuery("");
				}
			}
		} catch (error) {
			// Invalid query params - log but don't crash
			console.warn("Invalid connector popup query params:", error);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [searchParams, allConnectors]);

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
		async (connector: (typeof OAUTH_CONNECTORS)[0]) => {
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

	// Handle starting indexing
	const handleStartIndexing = useCallback(async (refreshConnectors: () => void) => {
		if (!indexingConfig || !searchSpaceId) return;

		// Validate date range
		const dateRangeValidation = dateRangeSchema.safeParse({ startDate, endDate });
		if (!dateRangeValidation.success) {
			toast.error(dateRangeValidation.error.errors[0]?.message || "Invalid date range");
			return;
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

			if (periodicEnabled) {
				const frequency = parseInt(frequencyMinutes, 10);
				await updateConnector({
					id: indexingConfig.connectorId,
					data: {
						periodic_indexing_enabled: true,
						indexing_frequency_minutes: frequency,
					},
				});
			}

			await indexConnector({
				connector_id: indexingConfig.connectorId,
				queryParams: {
					search_space_id: searchSpaceId,
					start_date: startDateStr,
					end_date: endDateStr,
				},
			});

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
	}, [indexingConfig, searchSpaceId, startDate, endDate, indexConnector, updateConnector, periodicEnabled, frequencyMinutes, getFrequencyLabel, router]);

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
				if (!isStartingIndexing) {
					setIndexingConfig(null);
					setStartDate(undefined);
					setEndDate(undefined);
					setPeriodicEnabled(false);
					setFrequencyMinutes("1440");
				}
			}
		},
		[activeTab, isStartingIndexing]
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
		startDate,
		endDate,
		isStartingIndexing,
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
		
		// Handlers
		handleOpenChange,
		handleTabChange,
		handleScroll,
		handleConnectOAuth,
		handleStartIndexing,
		handleSkipIndexing,
	};
};

