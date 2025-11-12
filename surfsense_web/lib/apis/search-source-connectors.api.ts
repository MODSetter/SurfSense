import { Connector, CreateConnectorRequest } from "@/hooks/use-connectors";

export const createConnector = async (
  data: CreateConnectorRequest,
  authToken: string
): Promise<Connector> => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to create connector");
  }

  return response.json();
};

export const getConnectors = async (
  skip = 0,
  limit = 100,
  authToken: string
): Promise<Connector[]> => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors?skip=${skip}&limit=${limit}`,
    {
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    }
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to fetch connectors");
  }

  return response.json();
};

export const getConnector = async (
  connectorId: number,
  authToken: string
): Promise<Connector> => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
    {
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    }
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to fetch connector");
  }

  return response.json();
};

export const updateConnector = async (
  connectorId: number,
  data: CreateConnectorRequest,
  authToken: string
): Promise<Connector> => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to update connector");
  }

  return response.json();
};

export const deleteConnector = async (
  connectorId: number,
  authToken: string
): Promise<void> => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    }
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to delete connector");
  }
};
