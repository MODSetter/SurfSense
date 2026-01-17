/**
 * Get auth token for Electric SQL
 * In production, this should get the token from your auth system
 */

export async function getElectricAuthToken(): Promise<string> {
	// For insecure mode (development), return empty string
	if (process.env.NEXT_PUBLIC_ELECTRIC_AUTH_MODE === "insecure") {
		return "";
	}

	// In production, get token from your auth system
	// This should match your backend auth token
	if (typeof window !== "undefined") {
		const token = localStorage.getItem("surfsense_bearer_token");
		return token || "";
	}

	return "";
}
