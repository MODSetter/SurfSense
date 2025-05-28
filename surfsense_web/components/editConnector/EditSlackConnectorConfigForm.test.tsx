import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event'; // For more realistic interactions with Select
import EditSlackConnectorConfigForm from './EditSlackConnectorConfigForm';
import { SearchSourceConnector } from '@/hooks/useSearchSourceConnectors'; // Adjust path as needed

// Mock UI components that are not part of the core logic being tested, if necessary
// For ShadCN components, often direct interaction is fine, but sometimes they need setup.
// For this test, we'll assume direct interaction works.
// jest.mock("@/components/ui/input", () => (props: any) => <input {...props} data-testid={props.id || 'input-mock'} />);
// jest.mock("@/components/ui/checkbox", () => (props: any) => <input type="checkbox" {...props} data-testid={props.id || 'checkbox-mock'} />);
// jest.mock("@/components/ui/select", () => ({
//   Select: (props: any) => <div data-testid={props.id || 'select-mock'}>{props.children}</div>,
//   SelectTrigger: (props: any) => <button {...props}>{props.children}</button>,
//   SelectValue: (props: any) => <div {...props}>{props.placeholder}</div>,
//   SelectContent: (props: any) => <div {...props}>{props.children}</div>,
//   SelectItem: (props: any) => <option value={props.value} {...props}>{props.children}</option>,
// }));


const initialMockConfig = {
  SLACK_BOT_TOKEN: 'xoxb-initial-token',
  slack_membership_filter_type: 'all_member_channels',
  slack_selected_channel_ids: ['C123', 'C456'],
  slack_initial_indexing_days: 30,
  slack_initial_max_messages_per_channel: 1000,
  slack_periodic_indexing_enabled: false,
  slack_periodic_indexing_frequency: 'daily',
  slack_max_messages_per_channel_periodic: 100,
};

const mockConnector: SearchSourceConnector = {
  id: 1,
  name: 'Slack Test Connector',
  connector_type: 'SLACK_CONNECTOR',
  is_indexable: true,
  last_indexed_at: null,
  config: { ...initialMockConfig },
  user_id: 'user1',
  created_at: new Date().toISOString(),
};

describe('EditSlackConnectorConfigForm', () => {
  let mockOnConfigChange: jest.Mock;

  beforeEach(() => {
    mockOnConfigChange = jest.fn();
  });

  test('renders all form fields correctly with initial values', () => {
    render(
      <EditSlackConnectorConfigForm
        connector={mockConnector}
        onConfigChange={mockOnConfigChange}
        disabled={false}
      />
    );

    // Authentication
    expect(screen.getByLabelText(/Slack Bot Token/i)).toHaveValue(initialMockConfig.SLACK_BOT_TOKEN);

    // Initial Indexing Settings
    expect(screen.getByText('Index All Channels Where Bot is Member')).toBeInTheDocument(); // For Select value display
    expect(screen.getByText(/Channel selection is managed in the 'Channels' tab/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Initial Indexing Period \(days\)/i)).toHaveValue(initialMockConfig.slack_initial_indexing_days);
    expect(screen.getByLabelText(/Max Messages Per Channel \(Initial Sync\)/i)).toHaveValue(initialMockConfig.slack_initial_max_messages_per_channel);
    
    // Periodic Indexing Settings
    const periodicCheckbox = screen.getByLabelText(/Enable Periodic Indexing/i) as HTMLInputElement;
    expect(periodicCheckbox.checked).toBe(initialMockConfig.slack_periodic_indexing_enabled);
    
    // Periodic fields should initially be hidden if checkbox is false
    if (!initialMockConfig.slack_periodic_indexing_enabled) {
      expect(screen.queryByLabelText(/Periodic Indexing Frequency/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/Max Messages Per Channel \(Periodic Sync\)/i)).not.toBeInTheDocument();
    }
  });

  test('calls onConfigChange with updated config for SLACK_BOT_TOKEN', () => {
    render(
      <EditSlackConnectorConfigForm
        connector={mockConnector}
        onConfigChange={mockOnConfigChange}
        disabled={false}
      />
    );
    const tokenInput = screen.getByLabelText(/Slack Bot Token/i);
    fireEvent.change(tokenInput, { target: { value: 'new-token' } });
    expect(mockOnConfigChange).toHaveBeenCalledWith(
      expect.objectContaining({ SLACK_BOT_TOKEN: 'new-token' })
    );
  });
  
  test('calls onConfigChange for slack_initial_indexing_days', () => {
    render(<EditSlackConnectorConfigForm connector={mockConnector} onConfigChange={mockOnConfigChange} disabled={false} />);
    const input = screen.getByLabelText(/Initial Indexing Period \(days\)/i);
    fireEvent.change(input, { target: { value: '10' } });
    expect(mockOnConfigChange).toHaveBeenCalledWith(expect.objectContaining({ slack_initial_indexing_days: 10 }));
    
    fireEvent.change(input, { target: { value: '-1' } });
    expect(mockOnConfigChange).toHaveBeenCalledWith(expect.objectContaining({ slack_initial_indexing_days: -1 }));

    fireEvent.change(input, { target: { value: '' } }); // Empty value
    expect(mockOnConfigChange).toHaveBeenCalledWith(expect.objectContaining({ slack_initial_indexing_days: null }));
  });

  test('calls onConfigChange for slack_initial_max_messages_per_channel', () => {
    render(<EditSlackConnectorConfigForm connector={mockConnector} onConfigChange={mockOnConfigChange} disabled={false} />);
    const input = screen.getByLabelText(/Max Messages Per Channel \(Initial Sync\)/i);
    fireEvent.change(input, { target: { value: '500' } });
    expect(mockOnConfigChange).toHaveBeenCalledWith(expect.objectContaining({ slack_initial_max_messages_per_channel: 500 }));
  });

  test('calls onConfigChange for slack_membership_filter_type', async () => {
    render(<EditSlackConnectorConfigForm connector={mockConnector} onConfigChange={mockOnConfigChange} disabled={false} />);
    
    // For ShadCN Select, we need to click the trigger, then the item.
    // `userEvent` is better for this, but `fireEvent` can also work.
    const selectTrigger = screen.getByRole('combobox', { name: /Channel Indexing Behavior/i });
    await userEvent.click(selectTrigger);
    
    // Assuming SelectItem roles are 'option' or similar, and they are now in the document
    const option = await screen.findByText('Index Only Selected Channels'); // Wait for option to appear
    await userEvent.click(option);

    expect(mockOnConfigChange).toHaveBeenCalledWith(
      expect.objectContaining({ slack_membership_filter_type: 'selected_member_channels' })
    );
  });
  
  test('shows/hides periodic indexing fields and calls onConfigChange', async () => {
    render(<EditSlackConnectorConfigForm connector={mockConnector} onConfigChange={mockOnConfigChange} disabled={false} />);
    const periodicCheckbox = screen.getByLabelText(/Enable Periodic Indexing/i);

    // Initially periodic fields are not visible (as per initialMockConfig)
    expect(screen.queryByLabelText(/Periodic Indexing Frequency/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Max Messages Per Channel \(Periodic Sync\)/i)).not.toBeInTheDocument();

    // Check the checkbox
    fireEvent.click(periodicCheckbox);
    expect(mockOnConfigChange).toHaveBeenCalledWith(
      expect.objectContaining({ slack_periodic_indexing_enabled: true })
    );
    
    // Now the fields should be visible
    const frequencySelect = await screen.findByLabelText(/Periodic Indexing Frequency/i); // Wait for it
    const maxMessagesInput = screen.getByLabelText(/Max Messages Per Channel \(Periodic Sync\)/i);
    expect(frequencySelect).toBeInTheDocument();
    expect(maxMessagesInput).toBeInTheDocument();

    // Change frequency
    const freqSelectTrigger = screen.getByRole('combobox', { name: /Periodic Indexing Frequency/i });
    await userEvent.click(freqSelectTrigger);
    const weeklyOption = await screen.findByText('Weekly');
    await userEvent.click(weeklyOption);
    expect(mockOnConfigChange).toHaveBeenCalledWith(
      expect.objectContaining({ slack_periodic_indexing_frequency: 'weekly', slack_periodic_indexing_enabled: true })
    );

    // Change max messages periodic
    fireEvent.change(maxMessagesInput, { target: { value: '75' } });
    expect(mockOnConfigChange).toHaveBeenCalledWith(
      expect.objectContaining({ slack_max_messages_per_channel_periodic: 75, slack_periodic_indexing_enabled: true })
    );

    // Uncheck the checkbox
    fireEvent.click(periodicCheckbox);
    expect(mockOnConfigChange).toHaveBeenCalledWith(
      expect.objectContaining({ slack_periodic_indexing_enabled: false })
    );
    
    // Fields should be hidden again
    expect(screen.queryByLabelText(/Periodic Indexing Frequency/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Max Messages Per Channel \(Periodic Sync\)/i)).not.toBeInTheDocument();
  });

  test('preserves other config values when one changes', () => {
    render(<EditSlackConnectorConfigForm connector={mockConnector} onConfigChange={mockOnConfigChange} disabled={false} />);
    const tokenInput = screen.getByLabelText(/Slack Bot Token/i);
    fireEvent.change(tokenInput, { target: { value: 'new-xoxb-token' } });

    expect(mockOnConfigChange).toHaveBeenCalledWith({
      ...initialMockConfig, // All original values
      SLACK_BOT_TOKEN: 'new-xoxb-token', // Only this one changed
    });
  });
  
  test('disables all form fields when disabled prop is true', () => {
    render(<EditSlackConnectorConfigForm connector={mockConnector} onConfigChange={mockOnConfigChange} disabled={true} />);
    
    expect(screen.getByLabelText(/Slack Bot Token/i)).toBeDisabled();
    expect(screen.getByRole('combobox', { name: /Channel Indexing Behavior/i })).toBeDisabled();
    expect(screen.getByLabelText(/Initial Indexing Period \(days\)/i)).toBeDisabled();
    expect(screen.getByLabelText(/Max Messages Per Channel \(Initial Sync\)/i)).toBeDisabled();
    expect(screen.getByLabelText(/Enable Periodic Indexing/i)).toBeDisabled();
    
    // If periodic indexing was enabled by default in mock, check those too
    const connectorWithPeriodicEnabled = {
        ...mockConnector,
        config: { ...mockConnector.config, slack_periodic_indexing_enabled: true }
    };
    render(<EditSlackConnectorConfigForm connector={connectorWithPeriodicEnabled} onConfigChange={mockOnConfigChange} disabled={true} />);
    expect(screen.getByRole('combobox', { name: /Periodic Indexing Frequency/i })).toBeDisabled();
    expect(screen.getByLabelText(/Max Messages Per Channel \(Periodic Sync\)/i)).toBeDisabled();
  });

  test('handles empty string for number inputs correctly by converting to null', () => {
    render(<EditSlackConnectorConfigForm connector={mockConnector} onConfigChange={mockOnConfigChange} disabled={false} />);
    const initialDaysInput = screen.getByLabelText(/Initial Indexing Period \(days\)/i);
    fireEvent.change(initialDaysInput, { target: { value: '' } });
    expect(mockOnConfigChange).toHaveBeenCalledWith(expect.objectContaining({ slack_initial_indexing_days: null }));

    const initialMaxMessagesInput = screen.getByLabelText(/Max Messages Per Channel \(Initial Sync\)/i);
    fireEvent.change(initialMaxMessagesInput, { target: { value: '' } });
    expect(mockOnConfigChange).toHaveBeenCalledWith(expect.objectContaining({ slack_initial_max_messages_per_channel: null }));

    // Enable periodic to test that field
    const periodicCheckbox = screen.getByLabelText(/Enable Periodic Indexing/i);
    fireEvent.click(periodicCheckbox); // Enable
    
    const periodicMaxMessagesInput = screen.getByLabelText(/Max Messages Per Channel \(Periodic Sync\)/i);
    fireEvent.change(periodicMaxMessagesInput, { target: { value: '' } });
    expect(mockOnConfigChange).toHaveBeenCalledWith(expect.objectContaining({ slack_max_messages_per_channel_periodic: null }));
  });

});
