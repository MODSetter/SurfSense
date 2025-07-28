"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

// Loading component with animation
const LoadingComponent = () => (
	<div className="flex flex-col justify-center items-center min-h-screen">
		<div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4"></div>
		<p className="text-muted-foreground">Loading API Key Management...</p>
	</div>
);

// Dynamically import the ApiKeyClient component
const ApiKeyClient = dynamic(() => import("./api-key-client"), {
	ssr: false,
	loading: () => <LoadingComponent />,
});

export default function ClientWrapper() {
	const [isMounted, setIsMounted] = useState(false);

	useEffect(() => {
		setIsMounted(true);
	}, []);

	if (!isMounted) {
		return <LoadingComponent />;
	}

	return <ApiKeyClient />;
}
