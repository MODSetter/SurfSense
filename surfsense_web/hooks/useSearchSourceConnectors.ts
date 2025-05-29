import { useState, useEffect, useCallback } from 'react';

export interface SearchSourceConnector {
  id: number;
  name: string;
  connector_type: string;
  is_indexable: boolean;
  last_indexed_at: string | null;
  config: Record<string, any>; // This allows any keys, including new Slack fields
  user_id?: string;
  created_at?: string;
}

// Interface for Slack channel discovery
export interface SlackChannelInfo {
  id: string;
  name: string;
  is_private: boolean;
  is_member: boolean;
}

// Interface for re-indexing request payload (though used internally)
interface ReindexSlackChannelsPayload {
  channel_ids: string[];
  force_reindex_all_messages?: boolean;
  reindex_start_date?: string | null; // Allow null to be passed if date is empty
  reindex_latest_date?: string | null; // Allow null to be passed if date is empty
}

export interface ConnectorSourceItem {
  id: number;
  name: string;
  type: string;
  sources: any[];
}

/**
 * Hook to fetch search source connectors from the API
 */
export const useSearchSourceConnectors = () => {
  const [connectors, setConnectors] = useState<SearchSourceConnector[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [connectorSourceItems, setConnectorSourceItems] = useState<ConnectorSourceItem[]>([
    {
      id: 1,
      name: "Crawled URL",
      type: "CRAWLED_URL",
      sources: [],
    },
    {
      id: 2,
      name: "File",
      type: "FILE",
      sources: [],
    },
    {
      id: 3,
      name: "Extension",
      type: "EXTENSION",
      sources: [],
    },
    {
      id: 4,
      name: "Youtube Video",
      type: "YOUTUBE_VIDEO",
      sources: [],
    }
  ]);

  useEffect(() => {
    const fetchConnectors = async () => {
      try {
        setIsLoading(true);
        const token = localStorage.getItem('surfsense_bearer_token');
        
        if (!token) {
          throw new Error('No authentication token found');
        }

        const response = await fetch(
          `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch connectors: ${response.statusText}`);
        }

        const data = await response.json();
        setConnectors(data);
        
        // Update connector source items when connectors change
        updateConnectorSourceItems(data);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('An unknown error occurred'));
        console.error('Error fetching search source connectors:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchConnectors();
  }, []);
  
  // Update connector source items when connectors change
  const updateConnectorSourceItems = (currentConnectors: SearchSourceConnector[]) => {
    // Start with the default hardcoded connectors
    const defaultConnectors: ConnectorSourceItem[] = [
      {
        id: 1,
        name: "Crawled URL",
        type: "CRAWLED_URL",
        sources: [],
      },
      {
        id: 2,
        name: "File",
        type: "FILE",
        sources: [],
      },
      {
        id: 3,
        name: "Extension",
        type: "EXTENSION",
        sources: [],
      },
      {
        id: 4,
        name: "Youtube Video",
        type: "YOUTUBE_VIDEO",
        sources: [],
      }
    ];
    
    // Add the API connectors
    const apiConnectors: ConnectorSourceItem[] = currentConnectors.map((connector, index) => ({
      id: 1000 + index, // Use a high ID to avoid conflicts with hardcoded IDs
      name: connector.name,
      type: connector.connector_type,
      sources: [],
    }));
    
    setConnectorSourceItems([...defaultConnectors, ...apiConnectors]);
  };

  /**
   * Create a new search source connector
   */
  const createConnector = async (connectorData: Omit<SearchSourceConnector, 'id' | 'user_id' | 'created_at'>) => {
    try {
      const token = localStorage.getItem('surfsense_bearer_token');
      
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(connectorData)
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to create connector: ${response.statusText}`);
      }

      const newConnector = await response.json();
      const updatedConnectors = [...connectors, newConnector];
      setConnectors(updatedConnectors);
      updateConnectorSourceItems(updatedConnectors);
      return newConnector;
    } catch (err) {
      console.error('Error creating search source connector:', err);
      throw err;
    }
  };

  /**
   * Update an existing search source connector
   */
  const updateConnector = async (
    connectorId: number, 
    connectorData: Partial<Omit<SearchSourceConnector, 'id' | 'user_id' | 'created_at'>>
  ) => {
    try {
      const token = localStorage.getItem('surfsense_bearer_token');
      
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(connectorData)
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to update connector: ${response.statusText}`);
      }

      const updatedConnector = await response.json();
      const updatedConnectors = connectors.map(connector => 
        connector.id === connectorId ? updatedConnector : connector
      );
      setConnectors(updatedConnectors);
      updateConnectorSourceItems(updatedConnectors);
      return updatedConnector;
    } catch (err) {
      console.error('Error updating search source connector:', err);
      throw err;
    }
  };

  /**
   * Delete a search source connector
   */
  const deleteConnector = async (connectorId: number) => {
    try {
      const token = localStorage.getItem('surfsense_bearer_token');
      
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}`,
        {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to delete connector: ${response.statusText}`);
      }

      const updatedConnectors = connectors.filter(connector => connector.id !== connectorId);
      setConnectors(updatedConnectors);
      updateConnectorSourceItems(updatedConnectors);
    } catch (err) {
      console.error('Error deleting search source connector:', err);
      throw err;
    }
  };

  /**
   * Index content from a connector to a search space
   */
  const indexConnector = async (connectorId: number, searchSpaceId: string | number) => {
    try {
      const token = localStorage.getItem('surfsense_bearer_token');
      
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/search-source-connectors/${connectorId}/index?search_space_id=${searchSpaceId}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to index connector content: ${response.statusText}`);
      }

      const result = await response.json();
      
      // Update the connector's last_indexed_at timestamp
      const updatedConnectors = connectors.map(connector => 
        connector.id === connectorId 
          ? { ...connector, last_indexed_at: new Date().toISOString() } 
          : connector
      );
      setConnectors(updatedConnectors);
      
      return result;
    } catch (err) {
      console.error('Error indexing connector content:', err);
      throw err;
    }
  };

  /**
   * Get connector source items - memoized to prevent unnecessary re-renders
   */
  const getConnectorSourceItems = useCallback(() => {
    return connectorSourceItems;
  }, [connectorSourceItems]);

  // Helper function for authenticated fetch requests
  const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
    const token = localStorage.getItem('surfsense_bearer_token');
    if (!token) {
      throw new Error('No authentication token found');
    }

    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...options.headers,
    };

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
      const errorBody = await response.text(); // Try to get more error info
      throw new Error(`API request failed: ${response.statusText} - ${errorBody}`);
    }
    // For 202 or 204, response.json() will fail. Handle it.
    if (response.status === 202 || response.status === 204) {
        return null; // Or some specific success indicator
    }
    return response.json();
  };


  /**
   * Discover Slack channels for a given connector
   */
  const discoverSlackChannels = async (connectorId: number): Promise<SlackChannelInfo[]> => {
    try {
      const data = await fetchWithAuth(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/slack/${connectorId}/discover-channels`,
        { method: 'GET' }
      );
      // The backend route for discover-channels returns { channels: SlackChannelInfo[] }
      // So, we need to access data.channels
      return data.channels as SlackChannelInfo[]; 
    } catch (err) {
      console.error(`Error discovering Slack channels for connector ${connectorId}:`, err);
      throw err; // Re-throw to be handled by the caller
    }
  };

  /**
   * Trigger re-indexing for specific Slack channels
   */
  const reindexSlackChannels = async (
    connectorId: number,
    channelIds: string[],
    forceReindexAllMessages?: boolean,
    reindexStartDate?: string,
    reindexLatestDate?: string
  ): Promise<any> => {
    try {
      const payload: ReindexSlackChannelsPayload = {
        channel_ids: channelIds,
        force_reindex_all_messages: forceReindexAllMessages,
        reindex_start_date: reindexStartDate || null, // Ensure null if empty string
        reindex_latest_date: reindexLatestDate || null, // Ensure null if empty string
      };
      
      const result = await fetchWithAuth(
        `${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/slack/${connectorId}/reindex-channels`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      );
      return result; // Typically a success message or status
    } catch (err) {
      console.error(`Error re-indexing Slack channels for connector ${connectorId}:`, err);
      throw err; // Re-throw to be handled by the caller
    }
  };

  return {
    connectors,
    isLoading,
    error,
    createConnector,
    updateConnector,
    deleteConnector,
    indexConnector,
    getConnectorSourceItems,
    connectorSourceItems,
    discoverSlackChannels, // Export new function
    reindexSlackChannels,  // Export new function
  };
};