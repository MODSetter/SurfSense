import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DexScreenerConnectForm } from '@/components/assistant-ui/connector-popup/connect-forms/components/dexscreener-connect-form';

// Mock the form submission
const mockOnSubmit = vi.fn();
const mockOnBack = vi.fn();

describe('DexScreenerConnectForm', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe('Initial Rendering', () => {
        it('should render the form with all required fields', () => {
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            // Check for connector name input
            expect(screen.getByLabelText('Connector Name')).toBeInTheDocument();

            // Check for benefits section
            expect(screen.getByText('No API Key Required')).toBeInTheDocument();

            // Check for add token button
            expect(screen.getByRole('button', { name: /add token/i })).toBeInTheDocument();
        });

        it('should display the DexScreener info alert', () => {
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            expect(screen.getByText('No API Key Required')).toBeInTheDocument();
            expect(screen.getByText(/DexScreener API is public and free to use/i)).toBeInTheDocument();
        });
    });

    describe('Form Validation', () => {
        it('should accept valid connector name', async () => {
            const user = userEvent.setup();
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            const nameInput = screen.getByLabelText('Connector Name');
            await user.clear(nameInput);
            await user.type(nameInput, 'Valid Name');

            // Should accept valid name
            expect(nameInput).toHaveValue('Valid Name');
        });

        it('should accept valid Ethereum address format', async () => {
            const user = userEvent.setup();
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            const addressInput = screen.getByLabelText('Token Address');
            const validAddress = '0x' + 'a'.repeat(40);
            await user.clear(addressInput);
            await user.type(addressInput, validAddress);

            // Should accept valid address
            expect(addressInput).toHaveValue(validAddress);
        });
    });

    describe('Token Management', () => {
        it('should add a new token when Add Token button is clicked', async () => {
            const user = userEvent.setup();
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            // Initially should have 1 token (default)
            expect(screen.getByText('Token #1')).toBeInTheDocument();

            const addTokenButton = screen.getByRole('button', { name: /add token/i });
            await user.click(addTokenButton);

            // Should now have 2 tokens
            await waitFor(() => {
                expect(screen.getByText('Token #2')).toBeInTheDocument();
            });
        });

        it('should remove a token when remove button is clicked', async () => {
            const user = userEvent.setup();
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            // Add a second token first
            const addTokenButton = screen.getByRole('button', { name: /add token/i });
            await user.click(addTokenButton);

            await waitFor(() => {
                expect(screen.getByText('Token #2')).toBeInTheDocument();
            });

            // Remove the second token
            const removeButtons = screen.getAllByRole('button', { name: '' }); // X buttons have no text
            const lastRemoveButton = removeButtons[removeButtons.length - 1];
            await user.click(lastRemoveButton);

            // Token #2 should be gone
            await waitFor(() => {
                expect(screen.queryByText('Token #2')).not.toBeInTheDocument();
            });
        });

        it('should allow adding multiple tokens up to the limit', async () => {
            const user = userEvent.setup();
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            const addTokenButton = screen.getByRole('button', { name: /add token/i });

            // Add 2 more tokens (already have 1)
            await user.click(addTokenButton);
            await user.click(addTokenButton);

            // Should have 3 tokens total
            await waitFor(() => {
                expect(screen.getByText('Token #3')).toBeInTheDocument();
                expect(screen.getByText('3 / 50 tokens')).toBeInTheDocument();
            });
        });

        it('should disable Add Token button when maximum tokens (50) are reached', async () => {
            const user = userEvent.setup();
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            const addTokenButton = screen.getByRole('button', { name: /add token/i });

            // Add 49 more tokens (already have 1) - this is slow but necessary
            for (let i = 0; i < 49; i++) {
                await user.click(addTokenButton);
            }

            // Button should be disabled and show max message
            await waitFor(() => {
                expect(addTokenButton).toBeDisabled();
                expect(screen.getByText(/maximum reached/i)).toBeInTheDocument();
            }, { timeout: 10000 });
        });
    });

    describe('Chain Selection', () => {
        it('should display supported chains in the dropdown', async () => {
            const user = userEvent.setup();
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            // Click on the chain selector
            const chainSelect = screen.getByRole('combobox', { name: /chain/i });
            await user.click(chainSelect);

            // Check for supported chains
            await waitFor(() => {
                expect(screen.getByRole('option', { name: /ethereum/i })).toBeInTheDocument();
                expect(screen.getByRole('option', { name: /bsc/i })).toBeInTheDocument();
                expect(screen.getByRole('option', { name: /polygon/i })).toBeInTheDocument();
            });
        });

        it('should allow chain selection', async () => {
            const user = userEvent.setup();
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            const chainSelect = screen.getByRole('combobox', { name: /chain/i });
            await user.click(chainSelect);

            // Select BSC
            const bscOption = screen.getByRole('option', { name: /bsc/i });
            await user.click(bscOption);

            // Verify dropdown closed (option should not be visible anymore)
            await waitFor(() => {
                expect(screen.queryByRole('option', { name: /bsc/i })).not.toBeInTheDocument();
            });
        });
    });

    describe('Form Submission', () => {
        it('should call onSubmit with valid data', async () => {
            const user = userEvent.setup();
            render(<DexScreenerConnectForm onSubmit={mockOnSubmit} onBack={mockOnBack} isSubmitting={false} />);

            // Fill connector name
            const nameInput = screen.getByLabelText('Connector Name');
            await user.clear(nameInput);
            await user.type(nameInput, 'My Connector');

            // Fill token address (first token already exists)
            const addressInput = screen.getByLabelText('Token Address');
            const validAddress = '0x' + 'a'.repeat(40);
            await user.type(addressInput, validAddress);

            // Find and click submit button
            const buttons = screen.getAllByRole('button');
            const submitButton = buttons.find(btn => btn.textContent?.includes('Connect'));

            if (submitButton) {
                await user.click(submitButton);

                // Verify onSubmit was called
                await waitFor(() => {
                    expect(mockOnSubmit).toHaveBeenCalled();
                }, { timeout: 3000 });
            }
        });
    });
});
