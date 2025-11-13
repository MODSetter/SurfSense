export const fetchSearchSpaces = async () => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces`,
		{
			headers: {
				Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
			},
			method: "GET",
		}
	);

	if (!response.ok) {
		throw new Error("Not authenticated");
	}

	return await response.json();
};

export const deleteSearchSpace = async (id: number) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${id}`,
		{
			method: "DELETE",
			headers: {
				Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
			},
		}
	);

	if (!response.ok) {
		throw new Error("Failed to delete search space");
	}

	return await response.json();
};

export const createSearchSpace = async (data: { name: string; description: string }) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces`,
		{
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
			},
			body: JSON.stringify(data),
		}
	);

	if (!response.ok) {
		throw new Error("Failed to create search space");
	}

	return await response.json();
};

export const fetchSearchSpace = async (searchSpaceId: string) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}`,
		{
			headers: {
				Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
			},
			method: "GET",
		}
	);

	if (response.status === 401) {
		// Clear token and redirect to home
		localStorage.removeItem("surfsense_bearer_token");
		window.location.href = "/";
		throw new Error("Unauthorized: Redirecting to login page");
	}

	if (!response.ok) {
		throw new Error(`Failed to fetch search space: ${response.status}`);
	}

	return await response.json();
};

export const fetchSearchSpacePreferences = async (searchSpaceId: number, authToken: string) => {
	const response = await fetch(
		`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-spaces/${searchSpaceId}/llm-preferences`,
		{
			headers: {
				Authorization: `Bearer ${authToken}`,
			},
			method: "GET",
		}
	);

	if (!response.ok) {
		throw new Error("Failed to fetch LLM preferences");
	}

	return await response.json();
};
