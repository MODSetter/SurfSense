/**
 * @jest-environment jsdom
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useParams, useRouter } from 'next/navigation';
import { toast } from 'sonner';
import TrelloConnectorPage from '@/app/dashboard/[search_space_id]/connectors/add/trello-connector/page';
import { useSearchSourceConnectors } from '@/hooks/useSearchSourceConnectors';

// Mock Next.js hooks
jest.mock('next/navigation', () => ({
  useParams: jest.fn(),
  useRouter: jest.fn(),
}));

// Mock the toast function
jest.mock('sonner', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

// Mock the custom hook
jest.mock('@/hooks/useSearchSourceConnectors', () => ({
  useSearchSourceConnectors: jest.fn(),
}));

// Mock fetch
global.fetch = jest.fn();

const mockPush = jest.fn();
const mockBack = jest.fn();

const mockUseSearchSourceConnectors = {
  createConnector: jest.fn(),
  isLoading: false,
};

describe('TrelloConnectorPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useParams as jest.Mock).mockReturnValue({ search_space_id: '1' });
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      back: mockBack,
    });
    (useSearchSourceConnectors as jest.Mock).mockReturnValue(mockUseSearchSourceConnectors);
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders the page with correct title and description', () => {
    render(<TrelloConnectorPage />);

    expect(screen.getByText('Trello Connector')).toBeInTheDocument();
    expect(screen.getByText(/connect your trello boards/i)).toBeInTheDocument();
  });

  it('renders the form with required fields', () => {
    render(<TrelloConnectorPage />);

    expect(screen.getByLabelText(/connector name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/trello api key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/trello api token/i)).toBeInTheDocument();
  });

  it('shows validation errors for empty required fields', async () => {
    const user = userEvent.setup();
    render(<TrelloConnectorPage />);

    const submitButton = screen.getByRole('button', { name: /create connector/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/connector name must be at least 3 characters/i)).toBeInTheDocument();
      expect(screen.getByText(/api key is required/i)).toBeInTheDocument();
      expect(screen.getByText(/token is required/i)).toBeInTheDocument();
    });
  });

  it('validates connector name length', async () => {
    const user = userEvent.setup();
    render(<TrelloConnectorPage />);

    const nameInput = screen.getByLabelText(/connector name/i);
    await user.type(nameInput, 'ab'); // Less than 3 characters

    const submitButton = screen.getByRole('button', { name: /create connector/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/connector name must be at least 3 characters/i)).toBeInTheDocument();
    });
  });

  it('fetches Trello boards when credentials are provided', async () => {
    const user = userEvent.setup();
    const mockBoards = [
      { id: 'board1', name: 'Board 1' },
      { id: 'board2', name: 'Board 2' },
    ];

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    render(<TrelloConnectorPage />);

    const nameInput = screen.getByLabelText(/connector name/i);
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);

    await user.type(nameInput, 'My Trello Connector');
    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');

    // The form should automatically fetch boards when both credentials are filled
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

  it('displays fetched boards for selection', async () => {
    const user = userEvent.setup();
    const mockBoards = [
      { id: 'board1', name: 'Board 1' },
      { id: 'board2', name: 'Board 2' },
    ];

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    render(<TrelloConnectorPage />);

    const nameInput = screen.getByLabelText(/connector name/i);
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);

    await user.type(nameInput, 'My Trello Connector');
    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
      expect(screen.getByText('Board 2')).toBeInTheDocument();
    });
  });

  it('allows selecting and deselecting boards', async () => {
    const user = userEvent.setup();
    const mockBoards = [
      { id: 'board1', name: 'Board 1' },
      { id: 'board2', name: 'Board 2' },
    ];

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    render(<TrelloConnectorPage />);

    const nameInput = screen.getByLabelText(/connector name/i);
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);

    await user.type(nameInput, 'My Trello Connector');
    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
    });

    // Select a board
    const checkbox1 = screen.getByRole('checkbox', { name: /board 1/i });
    await user.click(checkbox1);

    expect(checkbox1).toBeChecked();

    // Deselect the board
    await user.click(checkbox1);

    expect(checkbox1).not.toBeChecked();
  });

  it('creates connector with selected boards', async () => {
    const user = userEvent.setup();
    const mockBoards = [
      { id: 'board1', name: 'Board 1' },
      { id: 'board2', name: 'Board 2' },
    ];

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    mockUseSearchSourceConnectors.createConnector.mockResolvedValueOnce({});

    render(<TrelloConnectorPage />);

    const nameInput = screen.getByLabelText(/connector name/i);
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);

    await user.type(nameInput, 'My Trello Connector');
    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
    });

    // Select a board
    const checkbox1 = screen.getByRole('checkbox', { name: /board 1/i });
    await user.click(checkbox1);

    // Submit the form
    const submitButton = screen.getByRole('button', { name: /create connector/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockUseSearchSourceConnectors.createConnector).toHaveBeenCalledWith({
        name: 'My Trello Connector',
        connector_type: 'TRELLO_CONNECTOR',
        config: {
          TRELLO_API_KEY: 'test_api_key',
          TRELLO_API_TOKEN: 'test_token',
          board_ids: ['board1'],
        },
        is_indexable: true,
      });
    });

    expect(toast.success).toHaveBeenCalledWith('Trello connector created successfully!');
    expect(mockPush).toHaveBeenCalledWith('/dashboard/1/connectors');
  });

  it('shows error when connector creation fails', async () => {
    const user = userEvent.setup();
    const mockBoards = [{ id: 'board1', name: 'Board 1' }];

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    mockUseSearchSourceConnectors.createConnector.mockRejectedValueOnce(
      new Error('Creation failed')
    );

    render(<TrelloConnectorPage />);

    const nameInput = screen.getByLabelText(/connector name/i);
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);

    await user.type(nameInput, 'My Trello Connector');
    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
    });

    const checkbox1 = screen.getByRole('checkbox', { name: /board 1/i });
    await user.click(checkbox1);

    const submitButton = screen.getByRole('button', { name: /create connector/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to create Trello connector');
    });
  });

  it('shows error when fetching boards fails', async () => {
    const user = userEvent.setup();

    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('API error'));

    render(<TrelloConnectorPage />);

    const nameInput = screen.getByLabelText(/connector name/i);
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);

    await user.type(nameInput, 'My Trello Connector');
    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Failed to fetch Trello boards');
    });
  });

  it('navigates back when back button is clicked', async () => {
    const user = userEvent.setup();
    render(<TrelloConnectorPage />);

    const backButton = screen.getByRole('button', { name: /back/i });
    await user.click(backButton);

    expect(mockBack).toHaveBeenCalled();
  });

  it('shows loading state during connector creation', async () => {
    const user = userEvent.setup();
    const mockBoards = [{ id: 'board1', name: 'Board 1' }];

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    // Mock loading state
    (useSearchSourceConnectors as jest.Mock).mockReturnValue({
      ...mockUseSearchSourceConnectors,
      isLoading: true,
    });

    render(<TrelloConnectorPage />);

    const nameInput = screen.getByLabelText(/connector name/i);
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);

    await user.type(nameInput, 'My Trello Connector');
    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
    });

    const checkbox1 = screen.getByRole('checkbox', { name: /board 1/i });
    await user.click(checkbox1);

    const submitButton = screen.getByRole('button', { name: /create connector/i });
    await user.click(submitButton);

    expect(screen.getByText(/creating connector/i)).toBeInTheDocument();
  });

  it('requires at least one board to be selected', async () => {
    const user = userEvent.setup();
    const mockBoards = [{ id: 'board1', name: 'Board 1' }];

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockBoards,
    });

    render(<TrelloConnectorPage />);

    const nameInput = screen.getByLabelText(/connector name/i);
    const apiKeyInput = screen.getByLabelText(/trello api key/i);
    const tokenInput = screen.getByLabelText(/trello api token/i);

    await user.type(nameInput, 'My Trello Connector');
    await user.type(apiKeyInput, 'test_api_key');
    await user.type(tokenInput, 'test_token');

    await waitFor(() => {
      expect(screen.getByText('Board 1')).toBeInTheDocument();
    });

    // Don't select any boards
    const submitButton = screen.getByRole('button', { name: /create connector/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/please select at least one board/i)).toBeInTheDocument();
    });
  });
});
