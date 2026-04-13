# UI Mockups - Story 1.2: DexScreener Connector Frontend

> [!NOTE]
> **Purpose**: Visual design specifications for DexScreener connector UI components
> 
> **Design System**: ShadCN UI with dark theme
> 
> **Reference**: Based on existing Luma connector patterns

---

## 1. Connect Form - Main Interface

![DexScreener Connect Form](file:///Users/mac_1/.gemini/antigravity/brain/02a071c7-57fc-4f43-a2e8-516ac511579a/dexscreener_connect_form_1769847937084.png)

### 📋 Component Breakdown

#### Header Section
- **Info Alert**: Light blue background với icon
  - Message: "No API Key Required - DexScreener API is free and public"
  - Purpose: Inform users về public API nature

#### Connector Name Section
- **Label**: "Connector Name"
- **Input Field**: Text input với placeholder "My DexScreener Connector"
- **Help Text**: "A friendly name to identify this connector"
- **Validation**: Required field

#### Token Management Section
- **Section Title**: "Tracked Tokens (2/50)"
  - Shows current count / maximum limit
- **Token Cards**: Stacked vertically
  - Each card contains:
    - Chain dropdown (Ethereum, BSC, Polygon, etc.)
    - Token address input (0x... format)
    - Optional name field
    - Delete button (red X icon)
- **Add Button**: Blue "+ Add Token" button
  - Disabled when limit reached (50 tokens)

#### Indexing Configuration
- **Date Range**: Two date pickers (Start Date, End Date)
- **Periodic Sync Toggle**: Switch component (enabled/disabled)
- **Sync Frequency**: Dropdown (Daily, Weekly, Monthly)

#### Benefits Section
- **Title**: "What you get with DexScreener integration:"
- **List Items**:
  - Access real-time crypto trading data across multiple chains
  - Track live token prices and market capitalization
  - Analyze liquidity pairs and trading volume trends
  - Monitor transaction history and large trades
  - Stay updated with new token listings and pair information

#### Action Button
- **Connect Button**: Blue, bottom-right alignment
- **States**: Default, Hover, Loading, Disabled

---

## 2. Token Card Component - Detailed View

![Token Card Component](file:///Users/mac_1/.gemini/antigravity/brain/02a071c7-57fc-4f43-a2e8-516ac511579a/dexscreener_token_card_1769847957474.png)

### 🎨 Design Specifications

#### Layout Structure
- **Container**: Horizontal layout với border và rounded corners
- **Left Section** (70% width):
  - Chain selector với logo icon
  - Token address input (monospace font)
  - Optional name input
- **Right Section** (30% width):
  - Delete button (circular, red X)

#### Validation States

**Valid Address**:
- Green checkmark icon next to address field
- Success message: "✓ Valid ERC-20 address"
- Green border on input field

**Invalid Address**:
- Red X icon next to address field
- Error message: "✗ Invalid address format"
- Red border on input field

**Empty State**:
- Neutral gray border
- Placeholder text: "0x..."

#### Chain Options
Support các chains:
- Ethereum (ETH)
- Binance Smart Chain (BSC)
- Polygon (MATIC)
- Arbitrum
- Optimism
- Avalanche
- Fantom
- Base

#### Interaction States
- **Hover**: Subtle background color change
- **Focus**: Blue border on active input
- **Delete Hover**: Red background on delete button

---

## 3. Config Edit Interface

![Config Edit Interface](file:///Users/mac_1/.gemini/antigravity/brain/02a071c7-57fc-4f43-a2e8-516ac511579a/dexscreener_config_edit_1769847978086.png)

### ⚙️ Configuration Management

#### Header
- **Title**: "Edit Connector"
- **Status Badge**: Green "Active" badge
  - Shows connector status (Active, Paused, Error)

#### Configuration Section
- **Connector Name**: Editable text input
- **Edit Icon**: Pencil icon for inline editing

#### Current Tokens Display
- **Section Title**: "Tracked Tokens (3)"
- **Token List**: Compact card view
  - Chain icon + name
  - Shortened address (0x1f98...F984)
  - Token name
  - Action icons (Edit, Delete)

#### Add New Token
- **Expandable Section**: "+ Add New Token" button
- **Expanded State**: Shows full token form
  - Same fields as connect form
  - Inline validation

#### Action Buttons
- **Cancel**: Gray button, left-aligned
  - Discards changes
  - Returns to connector list
- **Save Changes**: Blue button, right-aligned
  - Validates all fields
  - Updates connector config
  - Shows success toast

---

## 🎯 Implementation Notes

### Responsive Design
- **Desktop**: Full width form với side-by-side layouts
- **Tablet**: Stacked sections, maintained spacing
- **Mobile**: Single column, full-width inputs

### Accessibility
- **ARIA Labels**: All form fields có proper labels
- **Keyboard Navigation**: Tab order logical
- **Screen Reader**: Descriptive text cho all actions
- **Focus Indicators**: Visible focus states

### Validation Rules

**Connector Name**:
- Required field
- Min length: 3 characters
- Max length: 50 characters

**Token Address**:
- Required field
- Must start with "0x"
- Must be 42 characters (0x + 40 hex)
- Hex characters only (0-9, a-f, A-F)

**Token Limit**:
- Maximum 50 tokens per connector
- Minimum 1 token required

### Error Handling

**Network Errors**:
- Toast notification với retry option
- Form remains editable

**Validation Errors**:
- Inline error messages
- Red border on invalid fields
- Prevent form submission

**Success States**:
- Green toast notification
- Redirect to connector list
- Update connector status

---

## 📱 Mobile Considerations

### Touch Targets
- Minimum 44x44px for all interactive elements
- Increased spacing between tokens
- Larger delete buttons

### Form Layout
- Single column layout
- Full-width inputs
- Stacked date pickers
- Bottom sheet for chain selector

### Performance
- Lazy load token list (virtual scrolling)
- Debounced address validation
- Optimistic UI updates

---

## 🔄 State Management

### Form States
1. **Initial**: Empty form với default values
2. **Editing**: User input in progress
3. **Validating**: Checking address formats
4. **Submitting**: API call in progress
5. **Success**: Connector created/updated
6. **Error**: Validation or API error

### Token List States
1. **Empty**: No tokens added
2. **Adding**: New token form visible
3. **Editing**: Existing token being modified
4. **Deleting**: Confirmation dialog shown
5. **Maximum**: 50 tokens reached

---

## 🎨 Design Tokens

### Colors
- **Primary**: Blue (#3B82F6)
- **Success**: Green (#10B981)
- **Error**: Red (#EF4444)
- **Background**: Slate (#1E293B)
- **Border**: Slate (#334155)

### Typography
- **Headings**: Inter, 600 weight
- **Body**: Inter, 400 weight
- **Monospace**: JetBrains Mono (addresses)

### Spacing
- **Section Gap**: 24px
- **Input Gap**: 16px
- **Card Padding**: 16px
- **Button Padding**: 12px 24px

---

## ✅ Implementation Checklist

- [ ] Create `dexscreener-connect-form.tsx` component
- [ ] Implement token card component với validation
- [ ] Create `dexscreener-config.tsx` edit interface
- [ ] Add chain selector dropdown với icons
- [ ] Implement address validation logic
- [ ] Add form state management (React Hook Form)
- [ ] Create Zod validation schema
- [ ] Implement error handling và toast notifications
- [ ] Add responsive breakpoints
- [ ] Test accessibility compliance
- [ ] Add loading states
- [ ] Implement optimistic UI updates

---

## 📚 Reference Components

### Existing Patterns
- [luma-connect-form.tsx](file:///Users/mac_1/Documents/GitHub/SurfSense/surfsense_web/components/assistant-ui/connector-popup/connect-forms/components/luma-connect-form.tsx) - Form structure
- [luma-config.tsx](file:///Users/mac_1/Documents/GitHub/SurfSense/surfsense_web/components/assistant-ui/connector-popup/connector-configs/components/luma-config.tsx) - Config pattern
- [connector-benefits.ts](file:///Users/mac_1/Documents/GitHub/SurfSense/surfsense_web/components/assistant-ui/connector-popup/connect-forms/connector-benefits.ts) - Benefits system

### Design System
- ShadCN UI components
- Tailwind CSS utilities
- Radix UI primitives
