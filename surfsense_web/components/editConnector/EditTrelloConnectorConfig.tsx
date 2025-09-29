import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { TrelloBoard } from "./types";
import { toast } from "sonner";

const trelloCredentialsSchema = z.object({
  trello_api_key: z.string().min(1, "API Key is required."),
  trello_api_token: z.string().min(1, "Token is required."),
});
type TrelloCredentialsFormValues = z.infer<typeof trelloCredentialsSchema>;

interface Props {
  connectorId: number;
  config: {
    trello_api_key?: string;
    trello_api_token?: string;
    selected_boards?: TrelloBoard[];
  };
  onConfigUpdate: (newConfig: any) => Promise<void>;
}

const EditTrelloConnectorConfig: React.FC<Props> = ({
  connectorId,
  config,
  onConfigUpdate,
}) => {
  const [boards, setBoards] = useState<TrelloBoard[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedBoards, setSelectedBoards] = useState<TrelloBoard[]>(
    config.selected_boards || []
  );

  const form = useForm<TrelloCredentialsFormValues>({
    resolver: zodResolver(trelloCredentialsSchema),
    defaultValues: {
      trello_api_key: config.trello_api_key || "",
      trello_api_token: config.trello_api_token || "",
    },
  });

  const handleFetchBoards = async (values: TrelloCredentialsFormValues) => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/trello/boards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch Trello boards.");
      }

      const data: TrelloBoard[] = await response.json();
      setBoards(data);
      toast.success("Successfully fetched Trello boards.");
    } catch (error) {
      toast.error("Failed to fetch Trello boards.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleBoardSelection = (board: TrelloBoard) => {
    setSelectedBoards((prev) =>
      prev.find((b) => b.id === board.id)
        ? prev.filter((b) => b.id !== board.id)
        : [...prev, board]
    );
  };

  const handleSaveChanges = async () => {
    try {
      await onConfigUpdate({
        ...config,
        selected_boards: selectedBoards,
      });
      toast.success("Changes saved successfully.");
    } catch (error) {
      toast.error("Failed to save changes.");
    }
  };

  return (
    <div className="space-y-6">
      <Form {...form}>
        <form
          onSubmit={form.handleSubmit(handleFetchBoards)}
          className="space-y-4"
        >
          <FormField
            control={form.control}
            name="trello_api_key"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Trello API Key</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="trello_api_token"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Trello API Token</FormLabel>
                <FormControl>
                  <Input type="password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" disabled={isLoading}>
            {isLoading ? "Fetching..." : "Fetch Trello Boards"}
          </Button>
        </form>
      </Form>

      {boards.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-medium">Select Boards to Index</h3>
          <div className="space-y-2">
            {boards.map((board) => (
              <div key={board.id} className="flex items-center justify-between">
                <span>{board.name}</span>
                <Button
                  variant={
                    selectedBoards.find((b) => b.id === board.id)
                      ? "secondary"
                      : "outline"
                  }
                  onClick={() => handleToggleBoardSelection(board)}
                >
                  {selectedBoards.find((b) => b.id === board.id)
                    ? "Selected"
                    : "Select"}
                </Button>
              </div>
            ))}
          </div>
          <Button onClick={handleSaveChanges}>Save Changes</Button>
        </div>
      )}
    </div>
  );
};

export default EditTrelloConnectorConfig;
