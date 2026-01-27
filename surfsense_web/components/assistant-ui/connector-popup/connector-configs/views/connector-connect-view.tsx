"use client";

import { ArrowLeft } from "lucide-react";
import { type FC, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { EnumConnectorName } from "@/contracts/enums/connector";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { getConnectorTypeDisplay } from "@/lib/connectors/utils";
import { getConnectFormComponent } from "../../connect-forms";

interface ConnectorConnectViewProps {
	connectorType: string;
	onSubmit: (data: {
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
	}) => Promise<void>;
	onBack: () => void;
	isSubmitting: boolean;
}

export const ConnectorConnectView: FC<ConnectorConnectViewProps> = ({
	connectorType,
	onSubmit,
	onBack,
	isSubmitting,
}) => {
	// Get connector-specific form component
	const ConnectFormComponent = useMemo(
		() => getConnectFormComponent(connectorType),
		[connectorType]
	);

	const handleFormSubmit = () => {
		// Prevent multiple submissions
		if (isSubmitting) {
			return;
		}
		// Map connector types to their form IDs
		const formIdMap: Record<string, string> = {
			TAVILY_API: "tavily-connect-form",
			SEARXNG_API: "searxng-connect-form",
			LINKUP_API: "linkup-api-connect-form",
			BAIDU_SEARCH_API: "baidu-search-api-connect-form",
			ELASTICSEARCH_CONNECTOR: "elasticsearch-connect-form",
			BOOKSTACK_CONNECTOR: "bookstack-connect-form",
			GITHUB_CONNECTOR: "github-connect-form",
			LUMA_CONNECTOR: "luma-connect-form",
			CIRCLEBACK_CONNECTOR: "circleback-connect-form",
			MCP_CONNECTOR: "mcp-connect-form",
			OBSIDIAN_CONNECTOR: "obsidian-connect-form",
		};
		const formId = formIdMap[connectorType];
		if (formId) {
			const form = document.getElementById(formId) as HTMLFormElement;
			if (form) {
				form.requestSubmit();
			}
		}
	};

	if (!ConnectFormComponent) {
		return (
			<div className="flex-1 flex flex-col min-h-0 overflow-hidden p-6">
				<p className="text-sm text-muted-foreground mb-4">
					Connector form not found for type: {connectorType}
				</p>
				<Button onClick={onBack} variant="ghost">
					Back
				</Button>
			</div>
		);
	}

	return (
		<div className="flex-1 flex flex-col min-h-0 overflow-hidden">
			{/* Header */}
			<div className="flex-shrink-0 px-6 sm:px-12 pt-8 sm:pt-10">
				<button
					type="button"
					onClick={onBack}
					className="flex items-center gap-2 text-xs sm:text-sm text-muted-foreground hover:text-foreground mb-6 w-fit"
				>
					<ArrowLeft className="size-4" />
					Back to connectors
				</button>

				<div className="flex items-center gap-4 mb-6">
					<div className="flex h-14 w-14 items-center justify-center rounded-xl border border-slate-400/30">
						{getConnectorIcon(connectorType as EnumConnectorName, "h-7 w-7")}
					</div>
					<div>
						<h2 className="text-xl sm:text-2xl font-semibold tracking-tight">
							Connect{" "}
							{connectorType === "MCP_CONNECTOR"
								? "MCP Server"
								: getConnectorTypeDisplay(connectorType)}
						</h2>
						<p className="text-xs sm:text-base text-muted-foreground mt-1">
							Enter your connection details
						</p>
					</div>
				</div>
			</div>

			{/* Form Content - Scrollable */}
			<div className="flex-1 min-h-0 overflow-y-auto px-6 sm:px-12">
				<ConnectFormComponent
					onSubmit={onSubmit}
					onBack={onBack}
					isSubmitting={isSubmitting}
					onFormSubmit={handleFormSubmit}
				/>
			</div>

			{/* Fixed Footer - Action buttons */}
			<div className="flex-shrink-0 flex items-center justify-between px-6 sm:px-12 py-6 bg-muted border-t border-border">
				<Button
					variant="ghost"
					onClick={onBack}
					disabled={isSubmitting}
					className="text-xs sm:text-sm"
				>
					Cancel
				</Button>
				<Button
					onClick={handleFormSubmit}
					disabled={isSubmitting}
					className="text-xs sm:text-sm min-w-[140px] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none"
				>
					{isSubmitting ? (
						<>
							<Spinner size="sm" className="mr-2" />
							Connecting
						</>
					) : connectorType === "MCP_CONNECTOR" ? (
						"Connect"
					) : (
						`Connect ${getConnectorTypeDisplay(connectorType)}`
					)}
				</Button>
			</div>
		</div>
	);
};
