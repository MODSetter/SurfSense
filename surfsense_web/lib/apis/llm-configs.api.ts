import { CreateLLMConfig, LLMConfig, UpdateLLMConfig } from "@/hooks/use-llm-configs";

export const fetchLLMConfigs = async (
  searchSpaceId: number,
  authToken: string
) => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/llm-configs?search_space_id=${searchSpaceId}`,
    {
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
      method: "GET",
    }
  );

  if (!response.ok) {
    throw new Error("Failed to fetch LLM configurations");
  }

  return await response.json();
};

export const createLLMConfig = async (
  config: CreateLLMConfig,
  authToken: string
): Promise<LLMConfig | null> => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/llm-configs`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify(config),
    }
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to create LLM configuration");
  }

  const newConfig = await response.json();

  return newConfig;
};

export const deleteLLMConfig = async (
  id: number,
  authToken: string
): Promise<boolean> => {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/llm-configs/${id}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error("Failed to delete LLM configuration");
  }

  return await response.json();
};

export const updateLLMConfig = async (
  id: number,
  config: UpdateLLMConfig,
  authToken: string
): Promise<LLMConfig | null> => {

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/llm-configs/${id}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify(config),
    }
  );

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to update LLM configuration");
  }

  const updatedConfig = await response.json();

  return updatedConfig;

};
