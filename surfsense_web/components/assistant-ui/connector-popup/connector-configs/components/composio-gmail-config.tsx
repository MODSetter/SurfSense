"use client";

import type { FC } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

interface ComposioGmailConfigProps {
	connector: SearchSourceConnector;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onNameChange?: (name: string) => void;
}

export const ComposioGmailConfig: FC<ComposioGmailConfigProps> = () => {
	return <div className="space-y-6" />;
};
