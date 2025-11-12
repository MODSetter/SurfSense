import type { ChatDetails } from "@/app/dashboard/[search_space_id]/chats/chats-client";

export const fetchChatDetails = async (
  chatId: string,
  authToken: string
): Promise<ChatDetails | null> => {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${Number(
        chatId
      )}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to fetch chat details: ${response.statusText}`);
    }

    return await response.json();
  } catch (err) {
    console.error("Error fetching chat details:", err);
    return null;
  }
};

export const fetchChatsBySearchSpace = async (
  searchSpaceId: string,
  authToken: string
): Promise<ChatDetails[] | null> => {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats?search_space_id=${searchSpaceId}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
      }
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch chats: ${response.statusText}`);
    }

    return await response.json();
  } catch (err) {
    console.error("Error fetching chats:", err);
    return null;
  }
};
