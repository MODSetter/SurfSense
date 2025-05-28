import { renderHook, act, waitFor } from '@testing-library/react';
import { useSearchSourceConnectors, SlackChannelInfo } from './useSearchSourceConnectors'; // Adjust path as needed

// Helper to create a mock response for fetch
const mockFetchResponse = (data: any, ok: boolean = true, status: number = 200) => {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)), // For error messages
  } as Response);
};

const mockFetchResponseNoContent = (ok: boolean = true, status: number = 202) => {
    return Promise.resolve({
      ok,
      status,
      json: () => Promise.reject(new Error("No JSON content")), // Should not be called for 202/204
      text: () => Promise.resolve(""), 
    } as Response);
  };

describe('useSearchSourceConnectors Hook - Slack Operations', () => {
  let mockFetch: jest.SpyInstance;
  let mockLocalStorageGetItem: jest.SpyInstance;

  const mockApiUrl = 'http://localhost:8000/api/v1'; // Example, ensure it matches env
  process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL = mockApiUrl;


  beforeEach(() => {
    // Spy on global fetch
    mockFetch = jest.spyOn(window, 'fetch');
    // Mock localStorage
    mockLocalStorageGetItem = jest.spyOn(Storage.prototype, 'getItem');
    mockLocalStorageGetItem.mockReturnValue('test-token'); // Default to having a token
  });

  afterEach(() => {
    mockFetch.mockRestore();
    mockLocalStorageGetItem.mockRestore();
  });

  describe('discoverSlackChannels', () => {
    test('successful API call returns channels and calls fetch correctly', async () => {
      const mockChannelsData: { channels: SlackChannelInfo[] } = {
        channels: [
          { id: 'C1', name: 'General', is_private: false, is_member: true },
          { id: 'C2', name: 'Random', is_private: true, is_member: true },
        ],
      };
      mockFetch.mockReturnValueOnce(mockFetchResponse(mockChannelsData));

      const { result } = renderHook(() => useSearchSourceConnectors());
      // Wait for initial connectors fetch to complete if any (though not directly tested here)
      await waitFor(() => expect(result.current.isLoading).toBe(false));


      let discoveredChannels: SlackChannelInfo[] = [];
      await act(async () => {
        discoveredChannels = await result.current.discoverSlackChannels(1);
      });
      
      expect(discoveredChannels).toEqual(mockChannelsData.channels);
      expect(mockFetch).toHaveBeenCalledWith(
        `${mockApiUrl}/slack/1/discover-channels`,
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    test('API error throws an error', async () => {
      mockFetch.mockReturnValueOnce(mockFetchResponse({ detail: 'API Error' }, false, 500));

      const { result } = renderHook(() => useSearchSourceConnectors());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await expect(result.current.discoverSlackChannels(1)).rejects.toThrow(
        /API request failed: Internal Server Error - {"detail":"API Error"}/
      );
    });

    test('no token throws an error', async () => {
      mockLocalStorageGetItem.mockReturnValueOnce(null); // No token

      const { result } = renderHook(() => useSearchSourceConnectors());
      // Initial fetch will fail here, which is fine for this test's focus
      await waitFor(() => expect(result.current.isLoading).toBe(false));


      await expect(result.current.discoverSlackChannels(1)).rejects.toThrow(
        'No authentication token found'
      );
      expect(mockFetch).not.toHaveBeenCalled(); // fetchWithAuth should prevent call
    });
  });

  describe('reindexSlackChannels', () => {
    test('successful API call (basic) calls fetch correctly', async () => {
      mockFetch.mockReturnValueOnce(mockFetchResponseNoContent(true, 202)); // 202 Accepted

      const { result } = renderHook(() => useSearchSourceConnectors());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.reindexSlackChannels(1, ['C1', 'C2']);
      });

      expect(mockFetch).toHaveBeenCalledWith(
        `${mockApiUrl}/slack/1/reindex-channels`,
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Authorization': 'Bearer test-token',
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify({
            channel_ids: ['C1', 'C2'],
            force_reindex_all_messages: undefined, // Explicitly undefined if not passed
            reindex_start_date: null, // Defaulted to null if not passed
            reindex_latest_date: null, // Defaulted to null if not passed
          }),
        })
      );
    });

    test('successful API call with all optional parameters', async () => {
      mockFetch.mockReturnValueOnce(mockFetchResponseNoContent(true, 202));

      const { result } = renderHook(() => useSearchSourceConnectors());
      await waitFor(() => expect(result.current.isLoading).toBe(false));
      
      await act(async () => {
        await result.current.reindexSlackChannels(
          1,
          ['C1'],
          true,
          '2023-01-01',
          '2023-01-31'
        );
      });

      expect(mockFetch).toHaveBeenCalledWith(
        `${mockApiUrl}/slack/1/reindex-channels`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            channel_ids: ['C1'],
            force_reindex_all_messages: true,
            reindex_start_date: '2023-01-01',
            reindex_latest_date: '2023-01-31',
          }),
        })
      );
    });
    
    test('handles empty date strings by passing null', async () => {
        mockFetch.mockReturnValueOnce(mockFetchResponseNoContent(true, 202));
  
        const { result } = renderHook(() => useSearchSourceConnectors());
        await waitFor(() => expect(result.current.isLoading).toBe(false));
        
        await act(async () => {
          await result.current.reindexSlackChannels(
            1,
            ['C1'],
            true,
            '', // Empty start date
            ''  // Empty latest date
          );
        });
  
        expect(mockFetch).toHaveBeenCalledWith(
          `${mockApiUrl}/slack/1/reindex-channels`,
          expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({
              channel_ids: ['C1'],
              force_reindex_all_messages: true,
              reindex_start_date: null, // Should be null
              reindex_latest_date: null, // Should be null
            }),
          })
        );
      });

    test('API error throws an error during reindex', async () => {
      mockFetch.mockReturnValueOnce(mockFetchResponse({ detail: 'Reindex Failed' }, false, 400));

      const { result } = renderHook(() => useSearchSourceConnectors());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await expect(result.current.reindexSlackChannels(1, ['C1'])).rejects.toThrow(
        /API request failed: Bad Request - {"detail":"Reindex Failed"}/
      );
    });

    test('no token throws an error during reindex', async () => {
      mockLocalStorageGetItem.mockReturnValueOnce(null); // No token

      const { result } = renderHook(() => useSearchSourceConnectors());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await expect(result.current.reindexSlackChannels(1, ['C1'])).rejects.toThrow(
        'No authentication token found'
      );
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });
  
  // Basic test for fetchWithAuth behavior (implicitly tested by others, but can be explicit)
  describe('fetchWithAuth internal behavior', () => {
    test('fetchWithAuth throws if no token', async () => {
      mockLocalStorageGetItem.mockReturnValueOnce(null);
      const { result } = renderHook(() => useSearchSourceConnectors());
      // The hook itself might make initial calls, let them pass/fail
      await waitFor(() => expect(result.current.isLoading).toBe(false)); 
      
      // Attempting any operation that uses fetchWithAuth internally should fail early
      // For example, discoverSlackChannels
      await expect(result.current.discoverSlackChannels(1)).rejects.toThrow('No authentication token found');
      expect(mockFetch).not.toHaveBeenCalled();
    });

    test('fetchWithAuth includes Authorization header', async () => {
      mockFetch.mockReturnValueOnce(mockFetchResponse({ channels: [] })); // For discoverSlackChannels
      const { result } = renderHook(() => useSearchSourceConnectors());
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      await act(async () => {
        await result.current.discoverSlackChannels(1);
      });

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: 'Bearer test-token' }),
        })
      );
    });
  });
});
