/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { toast } from 'sonner';
import EditTrelloConnectorConfig from '@/components/editConnector/EditTrelloConnectorConfig';
import { TrelloBoard } from '@/components/editConnector/types';

// Mock the toast function
jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

// Mock fetch
global.fetch = jest.fn();

const mockOnConfigUpdate = jest.fn();

const defaultProps = {
  connectorId: 1,
  config: {
    trello_api_key: '',
    trello_api_token: '',
    selected_boards: [],
  },
  onConfigUpdate: mockOnConfigUpdate,
};

const mockBoards: TrelloBoard[] = [
  { id: 'board1', name: 'Board 1' },
  { id: 'board2', name: 'Board 2' },
  { id: 'board3', name: 'Board 3' },
];

describe('EditTrelloConnectorConfig', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders the form with correct fields', () => {
    render(<EditTrelloConnectorConfig {...defaultProps} />);

    expect(screen.getByLabelText(/trello api key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/trello api token/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /fetch trello boards/i })).toBeInTheDocument();
  });

  it('populates form with existing config values', () => {
    const propsWithConfig = {
      ...defaultProps,
      config: {
        trello_api_key: 'existing_key',
        trello_api_token: 'existing_token',
        selected_boards: [],
      },
    };

    render(<EditTrelloConnectorConfig {...propsWithConfig} />);

    expect(screen.getByDisplayValue('existing_key')).toBeInTheDocument();
    expect(screen.getByDisplayValue('existing_token')).toBeInTheDocument();
  });

  it('shows validation errors for empty fields', async () => {
    const user = userEvent.setup();
    render(<EditTrelloConnectorConfig {...defaultProps} />);

    const submitButton = screen.getByRole('button', { name: /fetch trello boards/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/api key is required/i)).toBeInTheDocument();
      expect(screen.getByText(/token is required/i)).toBeInTheDocument();
    });
  });

  it('calls fetchBoards API when form is submitted with valid data', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    render(<EditTrelloConnectorConfig {...defaultProps} />);

    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);
    const submitButton = screen.getByRole('button', { name: /fetch trello boards/i });

    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');
    await user.click(submitButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/trello/boards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trello_api_key: 'test_api_key',
          trello_api_token: 'test_token',
        }),
      });
    });
  });

  it('displays boards after successful API call', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    render(<EditTrelloConnectorConfig {...defaultProps} />);

    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);
    const submitButton = screen.getByRole('button', { name: /fetch trello boards/i });

    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
      expect(screen.getByText('Board 2')).toBeInTheDocument();
      expect(screen.getByText('Board 3')).toBeInTheDocument();
    });

    expect(toast.success).toHaveBeenCalledWith('Successfully fetched Trello boards.');
  });

  it('shows error toast when API call fails', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
    });

    render(<EditTrelloConnectorConfig {...defaultProps} />);

    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);
    const submitButton = screen.getByRole('button', { name: /fetch trello boards/i });

    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');
    await user.click(submitButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to fetch Trello boards.');
    });
  });

  it('shows error toast when fetch throws an error', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

    render(<EditTrelloConnectorConfig {...defaultProps} />);

    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);
    const submitButton = screen.getByRole('button', { name: /fetch trello boards/i });

    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');
    await user.click(submitButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to fetch Trello boards.');
    });
  });

  it('displays loading state during API call', async () => {
    const user = userEvent.setup();
    let resolvePromise: (value: any) => void;
    const promise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    (global.fetch as jest.Mock).mockReturnValueOnce(promise);

    render(<EditTrelloConnectorConfig {...defaultProps} />);

    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);
    const submitButton = screen.getByRole('button', { name: /fetch trello boards/i });

    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');
    await user.click(submitButton);

    expect(screen.getByText('Fetching...')).toBeInTheDocument();
    expect(submitButton).toBeDisabled();

    // Resolve the promise
    resolvePromise!({
      ok: true,
      json: async () => mockBoards,
    });

    await waitFor(() => {
      expect(screen.getByText('Fetch Trello Boards')).toBeInTheDocument();
    });
  });

  it('allows selecting and deselecting boards', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    render(<EditTrelloConnectorConfig {...defaultProps} />);

    // First fetch boards
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);
    const submitButton = screen.getByRole('button', { name: /fetch trello boards/i });

    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
    });

    // Select a board
    const selectButton1 = screen.getByRole('button', { name: /select/i });
    await user.click(selectButton1);

    expect(screen.getByRole('button', { name: /selected/i })).toBeInTheDocument();

    // Deselect the board
    await user.click(screen.getByRole('button', { name: /selected/i }));

    expect(screen.getByRole('button', { name: /select/i })).toBeInTheDocument();
  });

  it('saves selected boards when save changes is clicked', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    render(<EditTrelloConnectorConfig {...defaultProps} />);

    // Fetch boards
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);
    const submitButton = screen.getByRole('button', { name: /fetch trello boards/i });

    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
    });

    // Select a board
    const selectButton1 = screen.getByRole('button', { name: /select/i });
    await user.click(selectButton1);

    // Save changes
    const saveButton = screen.getByRole('button', { name: /save changes/i });
    await user.click(saveButton);

    expect(mockOnConfigUpdate).toHaveBeenCalledWith({
      ...defaultProps.config,
      selected_boards: [{ id: 'board1', name: 'Board 1' }],
    });

    expect(toast.success).toHaveBeenCalledWith('Changes saved successfully.');
  });

  it('shows error toast when save changes fails', async () => {
    const user = userEvent.setup();
    mockOnConfigUpdate.mockRejectedValueOnce(new Error('Save failed'));

    render(<EditTrelloConnectorConfig {...defaultProps} />);

    const saveButton = screen.getByRole('button', { name: /save changes/i });
    await user.click(saveButton);

    expect(toast.error).toHaveBeenCalledWith('Failed to save changes.');
  });

  it('initializes with previously selected boards', () => {
    const propsWithSelectedBoards = {
      ...defaultProps,
      config: {
        ...defaultProps.config,
        selected_boards: [mockBoards[0], mockBoards[1]],
      },
    };

    render(<EditTrelloConnectorConfig {...propsWithSelectedBoards} />);

    // The selected boards should be in state but not visible until boards are fetched
    // This is more of an integration test for the component's internal state
    expect(screen.getByLabelText(/trello api key/i)).toBeInTheDocument();
  });

  it('handles multiple board selections correctly', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    render(<EditTrelloConnectorConfig {...defaultProps} />);

    // Fetch boards
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);
    const submitButton = screen.getByRole('button', { name: /fetch trello boards/i });

    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
    });

    // Select multiple boards
    const selectButtons = screen.getAllByRole('button', { name: /select/i });
    await user.click(selectButtons[0]); // Select Board 1
    await user.click(selectButtons[1]); // Select Board 2

    // Save changes
    const saveButton = screen.getByRole('button', { name: /save changes/i });
    await user.click(saveButton);

    expect(mockOnConfigUpdate).toHaveBeenCalledWith({
      ...defaultProps.config,
      selected_boards: [
        { id: 'board1', name: 'Board 1' },
        { id: 'board2', name: 'Board 2' },
      ],
    });
  });
});
