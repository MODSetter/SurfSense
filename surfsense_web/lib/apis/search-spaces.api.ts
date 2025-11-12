export const fetchSearchSpaces = async () => {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem(
            "surfsense_bearer_token"
          )}`,
        },
        method: "GET",
      }
    );

    if (!response.ok) {
      throw new Error("Not authenticated");
    }

    const data = await response.json();
    return data;
  } catch (err: any) {
    console.error("Error fetching search spaces:", err);
    return null;
  }
};

export const handleDeleteSearchSpace = async (id: number) => {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${id}`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${localStorage.getItem(
            "surfsense_bearer_token"
          )}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error("Failed to delete search space");
    }
  } catch (error) {
    console.error("Error deleting search space:", error);
    return;
  }
};

export const handleCreateSearchSpace = async (data: {
  name: string;
  description: string;
}) => {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem(
            "surfsense_bearer_token"
          )}`,
        },
        body: JSON.stringify(data),
      }
    );

    if (!response.ok) {
      throw new Error("Failed to create search space");
    }

    const result = await response.json();

    return result;
  } catch (error) {
    console.error("Error creating search space:", error);
    throw error;
  }
};

export const fetchSearchSpace = async (searchSpaceId: string) => {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem(
            "surfsense_bearer_token"
          )}`,
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

    const data = await response.json();
    return data;
  } catch (err: any) {
    console.error("Error fetching search space:", err);
  }
};
