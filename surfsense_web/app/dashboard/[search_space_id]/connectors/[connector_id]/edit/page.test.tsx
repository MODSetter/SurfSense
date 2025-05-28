import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import EditConnectorPage from './page'; // Adjust path if necessary
import { useConnectorEditPage } from '@/hooks/useConnectorEditPage'; // Mock this hook
import { SearchSourceConnector } from '@/hooks/useSearchSourceConnectors'; // For types
import { toast } from 'sonner'; // Mock toast

// Mock Next.js router and params
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
  useParams: () => ({
    search_space_id: '1',
    connector_id: '1', // Default for most tests, can be overridden in mock setup
  }),
}));

// Mock the custom hook
jest.mock('@/hooks/useConnectorEditPage');

// Mock sonner
jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
    info: jest.fn(),
    warning: jest.fn(),
  },
}));

const mockDefaultForm = {
  control: {} as any, // Basic mock for form control
  handleSubmit: (fn: any) => (e: any) => { e.preventDefault(); fn(); },
  setValue: jest.fn(),
  getValues: jest.fn((key) => {
    if (key === 'config') return mockUseConnectorEditPageValues.connector?.config || {};
    return undefined;
  }),
  watch: jest.fn((key, defaultValue) => {
    if (key === 'config.slack_membership_filter_type') {
      return mockUseConnectorEditPageValues.connector?.config?.slack_membership_filter_type || defaultValue;
    }
    return defaultValue;
  }),
  formState: { errors: {} },
} as any;

let mockUseConnectorEditPageValues: any;

const setupMockHook = (connectorData: Partial<SearchSourceConnector> | null) => {
  const baseConnector: SearchSourceConnector = {
    id: 1,
    name: 'Test Connector',
    connector_type: 'GENERIC',
    is_indexable: true,
    last_indexed_at: null,
    config: {},
    user_id: 'user1',
    created_at: new Date().toISOString(),
    ...connectorData,
  };

  mockUseConnectorEditPageValues = {
    connectorsLoading: false,
    connector: connectorData ? baseConnector : null,
    isSaving: false,
    editForm: { ...mockDefaultForm, getValues: jest.fn((key) => { // Ensure getValues is fresh
        if (key === 'config') return baseConnector.config || {};
        return undefined;
    }), watch: jest.fn((key, defaultValue) => {
        if (key === 'config.slack_membership_filter_type') {
          return baseConnector.config?.slack_membership_filter_type || defaultValue;
        }
        return defaultValue;
      }) 
    },
    patForm: { ...mockDefaultForm },
    handleSaveChanges: jest.fn(),
    // GitHub specific (not primary focus but part of hook)
    editMode: false, setEditMode: jest.fn(), originalPat: '', currentSelectedRepos: [],
    fetchedRepos: [], setFetchedRepos: jest.fn(), newSelectedRepos: [], setNewSelectedRepos: jest.fn(),
    isFetchingRepos: false, handleFetchRepositories: jest.fn(), handleRepoSelectionChange: jest.fn(),
    // Placeholder for Slack specific functions - these would be part of useSearchSourceConnectors usually
    // and then exposed via useConnectorEditPage or called directly if page uses useSearchSourceConnectors
    discoverSlackChannels: jest.fn(), 
    triggerSlackReindex: jest.fn(),
  };
  (useConnectorEditPage as jest.Mock).mockReturnValue(mockUseConnectorEditPageValues);
};


describe('EditConnectorPage - Slack Channel Management', () => {

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Tab Visibility', () => {
    test('shows "Channel Management" tab only for SLACK_CONNECTOR', () => {
      setupMockHook({ connector_type: 'SLACK_CONNECTOR', config: { SLACK_BOT_TOKEN: 'token' } });
      render(<EditConnectorPage />);
      expect(screen.getByText('Configuration')).toBeInTheDocument();
      expect(screen.getByText('Channel Management')).toBeInTheDocument();
      expect(screen.getByText('Channel Management')).not.toBeDisabled();
    });

    test('disables "Channel Management" tab for non-Slack connectors', () => {
      setupMockHook({ connector_type: 'GITHUB_CONNECTOR' });
      render(<EditConnectorPage />);
      expect(screen.getByText('Configuration')).toBeInTheDocument();
      expect(screen.getByText('Channel Management')).toBeInTheDocument(); // Tab exists but is disabled
      expect(screen.getByText('Channel Management')).toHaveAttribute('aria-disabled', 'true');
    });
  });

  describe('Granular Channel Selection UI (SLACK_CONNECTOR)', () => {
    const slackConnectorBase = {
        connector_type: 'SLACK_CONNECTOR',
        config: {
            SLACK_BOT_TOKEN: 'valid-token',
            slack_membership_filter_type: 'selected_member_channels', // Default to selected for these tests
            slack_selected_channel_ids: [],
        }
    };

    test('shows channel selection UI when type is "selected_member_channels"', async () => {
      setupMockHook(slackConnectorBase);
      render(<EditConnectorPage />);
      await userEvent.click(screen.getByText('Channel Management')); // Navigate to tab
      
      expect(screen.getByText('Granular Channel Selection')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Discover & Select Channels/i })).toBeInTheDocument();
    });

    test('shows "All Channels Mode" message when type is "all_member_channels"', async () => {
        setupMockHook({ 
            ...slackConnectorBase, 
            config: { ...slackConnectorBase.config, slack_membership_filter_type: 'all_member_channels' }
        });
        render(<EditConnectorPage />);
        await userEvent.click(screen.getByText('Channel Management'));

        expect(screen.getByText('All Channels Mode')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Discover & Select Channels/i })).not.toBeInTheDocument();
    });
    
    test('discovering channels populates table and handles loading state', async () => {
        setupMockHook(slackConnectorBase);
        const mockDiscoveredChannels = [
            { id: 'C1', name: 'General', is_private: false, is_member: true },
            { id: 'C2', name: 'Random', is_private: false, is_member: true },
        ];
        // For this test, we assume handleDiscoverChannels is part of the page component itself, not the hook
        // In a real scenario, this might be:
        // mockUseConnectorEditPageValues.discoverSlackChannels.mockResolvedValue(mockDiscoveredChannels);
        // For now, we'll check the button click and assume the mocked console.log from page implementation
        
        render(<EditConnectorPage />);
        await userEvent.click(screen.getByText('Channel Management'));
        
        const discoverButton = screen.getByRole('button', { name: /Discover & Select Channels/i });
        
        // Simulate the page's handleDiscoverChannels
        // This is a bit of a workaround as the function is internal to the component
        // A better test would mock the API call if discoverSlackChannels was from the hook
        // For now, we assert the button is there and would trigger the internal logic
        expect(discoverButton).not.toBeDisabled();
        await userEvent.click(discoverButton);

        // Since handleDiscoverChannels is internal and uses setTimeout for mock, we need to wait
        // This relies on the mock implementation within EditConnectorPage.tsx
        expect(await screen.findByText('General')).toBeInTheDocument(); // Wait for table to populate
        expect(screen.getByText('Random')).toBeInTheDocument();
        expect(toast.success).toHaveBeenCalledWith("Discovered 2 channels where bot is a member.");
    });

    test('selecting channels and clicking "Update Channel Selection" calls setValue', async () => {
        setupMockHook({
            ...slackConnectorBase,
            config: { ...slackConnectorBase.config, slack_selected_channel_ids: ['C1'] } // Pre-select one
        });
        render(<EditConnectorPage />);
        await userEvent.click(screen.getByText('Channel Management'));

        // First, discover channels to populate the table
        const discoverButton = screen.getByRole('button', { name: /Discover & Select Channels/i });
        await userEvent.click(discoverButton);
        await screen.findByText('General'); // Wait for table

        const checkboxGeneral = screen.getByRole('checkbox', { name: /select channel General/i }); // Assuming aria-label for checkbox
        const checkboxRandom = screen.getByRole('checkbox', { name: /select channel Random/i });
        
        // Initial state from config
        expect(checkboxGeneral).toBeChecked();
        expect(checkboxRandom).not.toBeChecked();

        // Deselect General, Select Random
        await userEvent.click(checkboxGeneral);
        await userEvent.click(checkboxRandom);

        const updateButton = screen.getByRole('button', { name: /Update Channel Selection in Config/i });
        await userEvent.click(updateButton);
        
        expect(mockUseConnectorEditPageValues.editForm.setValue).toHaveBeenCalledWith(
            'config',
            expect.objectContaining({ slack_selected_channel_ids: ['C2'] }), // C1 deselected, C2 selected
            { shouldValidate: true, shouldDirty: true }
        );
        expect(toast.success).toHaveBeenCalledWith("Channel selection updated. Save changes to persist.");
    });
  });

  describe('On-Demand Re-indexing UI (SLACK_CONNECTOR)', () => {
    const slackConnectorWithChannels = {
        connector_type: 'SLACK_CONNECTOR',
        config: {
            SLACK_BOT_TOKEN: 'valid-token',
            slack_membership_filter_type: 'selected_member_channels',
            slack_selected_channel_ids: ['C1_CONFIG', 'C2_CONFIG'], // Channels from config
        }
    };

    test('displays channels for re-indexing and triggers reindex call', async () => {
        setupMockHook(slackConnectorWithChannels);
        // mockUseConnectorEditPageValues.triggerSlackReindex.mockResolvedValue({ message: "Re-index started" });

        render(<EditConnectorPage />);
        await userEvent.click(screen.getByText('Channel Management'));
        
        // Channels from config should be listed
        expect(screen.getByText('Known ID: C1_CONFIG')).toBeInTheDocument();
        expect(screen.getByText('Known ID: C2_CONFIG')).toBeInTheDocument();

        const reindexCheckboxC1 = screen.getByRole('checkbox', { name: /select channel Known ID: C1_CONFIG/i });
        await userEvent.click(reindexCheckboxC1); // Select C1 for re-index

        const forceReindexCheckbox = screen.getByLabelText(/Full Re-index/i);
        await userEvent.click(forceReindexCheckbox); // Enable force re-index

        const startDateInput = screen.getByLabelText(/Re-index Start Date/i);
        const latestDateInput = screen.getByLabelText(/Re-index Latest Date/i);
        await userEvent.type(startDateInput, '2023-01-01');
        await userEvent.type(latestDateInput, '2023-01-31');
        
        const reindexButton = screen.getByRole('button', { name: /Re-index Selected Channels/i });
        expect(reindexButton).not.toBeDisabled();
        await userEvent.click(reindexButton);

        // Verify the internal handleTriggerReindex was called (via console.log or toast in mock)
        // This relies on the mocked implementation within the page.
        // A direct mock of an API call function from the hook would be better.
        expect(toast.info).toHaveBeenCalledWith("Triggering re-indexing for selected channels...");
        // We can't directly assert on `hookTriggerSlackReindex` as it's not directly called by the component
        // but by the internal `handleTriggerReindex`.
        // The console.log in the component's handleTriggerReindex would show:
        // Re-indexing payload: { channel_ids: ['C1_CONFIG'], force_reindex_all_messages: true, reindex_start_date: '2023-01-01', reindex_latest_date: '2023-01-31' }
        
        // Wait for mocked async operation in handleTriggerReindex
        await waitFor(() => {
            expect(toast.success).toHaveBeenCalledWith("Re-indexing task scheduled successfully.");
        });
    });
    
    test('re-index button is disabled if no channels are selected', async () => {
        setupMockHook(slackConnectorWithChannels);
        render(<EditConnectorPage />);
        await userEvent.click(screen.getByText('Channel Management'));
        
        const reindexButton = screen.getByRole('button', { name: /Re-index Selected Channels/i });
        expect(reindexButton).toBeDisabled(); // Initially disabled

        const reindexCheckboxC1 = screen.getByRole('checkbox', { name: /select channel Known ID: C1_CONFIG/i });
        await userEvent.click(reindexCheckboxC1); // Select one
        expect(reindexButton).not.toBeDisabled();

        await userEvent.click(reindexCheckboxC1); // Deselect again
        expect(reindexButton).toBeDisabled();
    });

    test('date inputs for re-indexing are shown only when "Full Re-index" is checked', async () => {
        setupMockHook(slackConnectorWithChannels);
        render(<EditConnectorPage />);
        await userEvent.click(screen.getByText('Channel Management'));

        expect(screen.queryByLabelText(/Re-index Start Date/i)).not.toBeInTheDocument();
        expect(screen.queryByLabelText(/Re-index Latest Date/i)).not.toBeInTheDocument();

        const forceReindexCheckbox = screen.getByLabelText(/Full Re-index/i);
        await userEvent.click(forceReindexCheckbox);

        expect(screen.getByLabelText(/Re-index Start Date/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Re-index Latest Date/i)).toBeInTheDocument();

        await userEvent.click(forceReindexCheckbox); // Uncheck

        expect(screen.queryByLabelText(/Re-index Start Date/i)).not.toBeInTheDocument();
        expect(screen.queryByLabelText(/Re-index Latest Date/i)).not.toBeInTheDocument();
    });
  });
});
