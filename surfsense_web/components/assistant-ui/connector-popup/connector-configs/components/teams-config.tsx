"use client";

import { Info } from "lucide-react";
import type { FC } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { ConnectorConfigProps } from "../index";

export interface TeamsConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const TeamsConfig: FC<TeamsConfigProps> = () => {
	return (
		<div className="space-y-6">
			<Alert>
				<Info />
				<AlertTitle>Microsoft Teams Access</AlertTitle>
				<AlertDescription>
					<p>
						Your agent can search and read messages from Teams channels you have access to, and send
						messages on your behalf. Make sure you&#39;re a member of the teams you want to interact
						with.
					</p>
				</AlertDescription>
			</Alert>
		</div>
	);
};
