"use client";

import type { FC } from "react";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";

interface ComposioCalendarConfigProps {
	connector: SearchSourceConnector;
	onConfigChange?: (config: Record<string, unknown>) => void;
	onNameChange?: (name: string) => void;
}

export const ComposioCalendarConfig: FC<ComposioCalendarConfigProps> = () => {
	return <div className="space-y-6" />;
};
