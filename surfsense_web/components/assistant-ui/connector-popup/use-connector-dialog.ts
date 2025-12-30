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
import { OAUTH_CONNECTORS } from "./connector-constants";
import type { IndexingConfigState } from "./connector-constants";

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
		const modalParam = searchParams.get("modal");
		const tabParam = searchParams.get("tab");
		const viewParam = searchParams.get("view");
		const connectorParam = searchParams.get("connector");
		
		if (modalParam === "connectors") {
			if (!isOpen) setIsOpen(true);
			
			if (tabParam === "active" || tabParam === "all") {
				if (activeTab !== tabParam) setActiveTab(tabParam);
			}
			
			if (viewParam === "configure" && connectorParam && !indexingConfig) {
				const oauthConnector = OAUTH_CONNECTORS.find(c => c.id === connectorParam);
				if (oauthConnector && allConnectors) {
					const existingConnector = allConnectors.find(
						(c: SearchSourceConnector) => c.connector_type === oauthConnector.connectorType
					);
					if (existingConnector) {
						setIndexingConfig({
							connectorType: oauthConnector.connectorType,
							connectorId: existingConnector.id,
							connectorTitle: oauthConnector.title,
						});
					}
				}
			}
		} else {
			if (isOpen) setIsOpen(false);
		}
	}, [searchParams, isOpen, activeTab, indexingConfig, allConnectors]);

	// Detect OAuth success and transition to config view
	useEffect(() => {
		const success = searchParams.get("success");
		const connectorParam = searchParams.get("connector");
		const modalParam = searchParams.get("modal");
		
		if (success === "true" && connectorParam && searchSpaceId && modalParam === "connectors") {
			const oauthConnector = OAUTH_CONNECTORS.find(c => c.id === connectorParam);
			if (oauthConnector) {
				refetchAllConnectors().then((result) => {
					const newConnector = result.data?.find(
						(c: SearchSourceConnector) => c.connector_type === oauthConnector.connectorType
					);
					if (newConnector) {
						setIndexingConfig({
							connectorType: oauthConnector.connectorType,
							connectorId: newConnector.id,
							connectorTitle: oauthConnector.title,
						});
						setIsOpen(true);
						const url = new URL(window.location.href);
						url.searchParams.delete("success");
						url.searchParams.set("view", "configure");
						window.history.replaceState({}, "", url.toString());
					}
				});
			}
		}
	}, [searchParams, searchSpaceId, refetchAllConnectors]);

	// Handle OAuth connection
	const handleConnectOAuth = useCallback(
		async (connector: (typeof OAUTH_CONNECTORS)[0]) => {
			if (!searchSpaceId || !connector.authEndpoint) return;

			try {
				setConnectingId(connector.id);
				const response = await authenticatedFetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}${connector.authEndpoint}?space_id=${searchSpaceId}`,
					{ method: "GET" }
				);

				if (!response.ok) {
					throw new Error(`Failed to initiate ${connector.title} OAuth`);
				}

				const data = await response.json();
				window.location.href = data.auth_url;
			} catch (error) {
				console.error(`Error connecting to ${connector.title}:`, error);
				toast.error(`Failed to connect to ${connector.title}`);
			} finally {
				setConnectingId(null);
			}
		},
		[searchSpaceId]
	);

	// Handle starting indexing
	const handleStartIndexing = useCallback(async (refreshConnectors: () => void) => {
		if (!indexingConfig || !searchSpaceId) return;

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

			setIndexingConfig(null);
			setStartDate(undefined);
			setEndDate(undefined);
			setPeriodicEnabled(false);
			setFrequencyMinutes("1440");
			
			const url = new URL(window.location.href);
			url.searchParams.delete("view");
			url.searchParams.delete("connector");
			url.searchParams.set("tab", "active");
			window.history.replaceState({}, "", url.toString());
			setActiveTab("active");
			
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
	}, [indexingConfig, searchSpaceId, startDate, endDate, indexConnector, updateConnector, periodicEnabled, frequencyMinutes, getFrequencyLabel]);

	// Handle skipping indexing
	const handleSkipIndexing = useCallback(() => {
		setIndexingConfig(null);
		setStartDate(undefined);
		setEndDate(undefined);
		setPeriodicEnabled(false);
		setFrequencyMinutes("1440");
		
		const url = new URL(window.location.href);
		url.searchParams.delete("view");
		url.searchParams.delete("connector");
		window.history.replaceState({}, "", url.toString());
	}, []);

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

