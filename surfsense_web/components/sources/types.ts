export interface Connector {
	id: string;
	title: string;
	description: string;
	icon: React.ReactNode;
	status: "available" | "coming-soon" | "connected";
}

export interface ConnectorCategory {
	id: string;
	title: string;
	connectors: Connector[];
}
