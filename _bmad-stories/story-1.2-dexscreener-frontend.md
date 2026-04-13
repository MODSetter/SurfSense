# Story 1.2: DexScreener Connector Frontend UI

## 📋 Story Overview

**Story ID**: 1.2  
**Story Title**: DexScreener Connector Frontend UI  
**Epic**: SurfSense Connectors Enhancement  
**Priority**: High  
**Status**: ✅ Implementation Complete (2026-02-01)  
**Created**: 2026-01-31  
**Depends On**: Story 1.1 (Backend API)

## 🎯 User Story

**As a** SurfSense user tracking cryptocurrency markets  
**I want** an intuitive UI to configure my DexScreener connector  
**So that** I can easily add/manage tracked tokens and view connector status

## 📝 Description

Implement frontend UI components for the DexScreener connector that allows users to:
1. Add new DexScreener connector with token configuration
2. Manage tracked tokens (add, edit, remove)
3. View connector status and indexed data
4. Configure periodic sync settings
5. Access connector documentation

This story implements the user-facing components following SurfSense's established connector UI patterns.

## ✅ Acceptance Criteria

### AC1: Connect Form Component ✅
- [x] User can access DexScreener connector from connector popup
- [x] Form includes connector name field (min 3 characters)
- [x] User can add multiple tokens (up to 50)
- [x] Each token has: chain selector, token address input, optional name
- [x] Form validates token addresses (40-character hex)
- [x] User can remove tokens from list
- [x] Date range selector for initial indexing
- [x] Periodic sync toggle with frequency selector
- [x] "What you get" benefits section displayed
- [x] Form submits to backend API endpoint

### AC2: Token Management UI ✅
- [x] Dynamic token list with add/remove buttons
- [x] Chain selector dropdown with popular chains:
  - Ethereum
  - BSC (Binance Smart Chain)
  - Polygon
  - Arbitrum
  - Optimism
  - Base
  - Avalanche
  - Solana
- [x] Token address input with validation
- [x] Optional token name/label field
- [x] Visual feedback for validation errors
- [x] Responsive design for mobile/desktop

### AC3: Connector Config Component ✅
- [x] Edit mode for existing connector
- [x] Update connector name
- [x] Add/remove tokens from tracked list
- [x] View current token configuration
- [x] Save changes button
- [x] Cancel/discard changes option

### AC4: Connector Benefits ✅
- [x] Display benefits list in connect form
- [x] Benefits include:
  - "Real-time cryptocurrency trading pair data"
  - "Track prices, volume, and liquidity across multiple DEXs"
  - "Search and analyze token market data with AI"
  - "Monitor your crypto portfolio with automated updates"
  - "Access historical price and volume trends"

### AC5: Documentation ✅
- [x] MDX documentation file created
- [x] Setup guide with screenshots
- [x] Token configuration instructions
- [x] Chain selection guide
- [x] Troubleshooting section
- [x] Link to DexScreener API docs

### AC6: Integration ✅
- [x] Connector registered in connector registry
- [x] Icon/logo added to public assets
- [x] Connector appears in connector list
- [x] Form properly integrated with connector popup
- [x] Config component properly integrated

## 🏗️ Technical Implementation

### 1. Connect Form Component
**File**: `surfsense_web/components/assistant-ui/connector-popup/connect-forms/components/dexscreener-connect-form.tsx`

**Component Structure**:
```typescript
export const DexScreenerConnectForm: FC<ConnectFormProps> = ({ onSubmit, isSubmitting }) => {
  // State management
  const [tokens, setTokens] = useState<TokenConfig[]>([]);
  const [startDate, setStartDate] = useState<Date | undefined>();
  const [endDate, setEndDate] = useState<Date | undefined>();
  const [periodicEnabled, setPeriodicEnabled] = useState(false);
  const [frequencyMinutes, setFrequencyMinutes] = useState("1440");
  
  // Form validation schema
  const formSchema = z.object({
    name: z.string().min(3),
    tokens: z.array(tokenSchema).min(1).max(50),
  });
  
  // Token management functions
  const addToken = () => { /* ... */ };
  const removeToken = (index: number) => { /* ... */ };
  const updateToken = (index: number, field: string, value: string) => { /* ... */ };
  
  // Submit handler
  const handleSubmit = async (values) => {
    await onSubmit({
      name: values.name,
      connector_type: EnumConnectorName.DEXSCREENER_CONNECTOR,
      config: { tokens: values.tokens },
      // ... other fields
    });
  };
};
```

**Token Config Schema**:
```typescript
interface TokenConfig {
  chain: string;
  address: string;
  name?: string;
}

const tokenSchema = z.object({
  chain: z.string().min(1, "Chain is required"),
  address: z.string().regex(/^0x[a-fA-F0-9]{40}$/, "Invalid token address"),
  name: z.string().optional(),
});
```

**UI Sections**:
1. **Alert**: Info about DexScreener API (no auth required)
2. **Connector Name**: Text input with validation
3. **Token List**: Dynamic list with add/remove
   - Chain selector (dropdown)
   - Token address input
   - Optional name field
   - Remove button
4. **Add Token Button**: Add new token to list
5. **Indexing Configuration**:
   - Date range selector
   - Periodic sync toggle
   - Frequency selector
6. **Benefits Section**: Display connector benefits

### 2. Connector Config Component
**File**: `surfsense_web/components/assistant-ui/connector-popup/connector-configs/components/dexscreener-config.tsx`

**Component Structure**:
```typescript
export const DexScreenerConfig: FC<ConnectorConfigProps> = ({ 
  connector, 
  onConfigChange, 
  onNameChange 
}) => {
  const [tokens, setTokens] = useState<TokenConfig[]>(
    connector.config?.tokens || []
  );
  const [name, setName] = useState(connector.name || "");
  
  // Update handlers
  const handleTokensChange = (newTokens: TokenConfig[]) => {
    setTokens(newTokens);
    onConfigChange({ ...connector.config, tokens: newTokens });
  };
  
  const handleNameChange = (newName: string) => {
    setName(newName);
    onNameChange?.(newName);
  };
};
```

**UI Sections**:
1. **Connector Name**: Editable text input
2. **Token Configuration**:
   - List of current tokens
   - Add/remove token functionality
   - Edit token details

### 3. Connector Benefits
**File**: `surfsense_web/components/assistant-ui/connector-popup/connect-forms/connector-benefits.ts`

**Add to benefits object**:
```typescript
DEXSCREENER_CONNECTOR: [
  "Real-time cryptocurrency trading pair data from multiple DEXs",
  "Track token prices, volume, and liquidity across chains",
  "Search and analyze market data with AI-powered insights",
  "Monitor your crypto portfolio with automated updates",
  "Access historical price trends and trading volumes",
],
```

### 4. Connector Registry
**Files to Update**:
- `surfsense_web/components/assistant-ui/connector-popup/connect-forms/index.tsx`
- `surfsense_web/components/assistant-ui/connector-popup/connector-configs/index.tsx`

**Register Components**:
```typescript
// In connect-forms/index.tsx
import { DexScreenerConnectForm } from "./components/dexscreener-connect-form";

// Add to component map
case EnumConnectorName.DEXSCREENER_CONNECTOR:
  return <DexScreenerConnectForm {...props} />;

// In connector-configs/index.tsx
import { DexScreenerConfig } from "./components/dexscreener-config";

// Add to component map
case EnumConnectorName.DEXSCREENER_CONNECTOR:
  return <DexScreenerConfig {...props} />;
```

### 5. Documentation
**File**: `surfsense_web/content/docs/connectors/dexscreener.mdx`

**Structure**:
```markdown
---
title: DexScreener
description: Connect DexScreener trading pair data to SurfSense
---

# DexScreener Integration Setup Guide

## How it works
- Fetches real-time trading pair data
- Tracks prices, volume, liquidity
- No API key required

## Authorization
No authentication needed - DexScreener API is public.

## Connecting to SurfSense
1. Navigate to Connector Dashboard
2. Select DexScreener Connector
3. Configure tracked tokens:
   - Select blockchain network
   - Enter token contract address
   - Add optional label
4. Configure sync settings
5. Click Connect

## What Gets Indexed
- Token pair information
- Price data (USD, native)
- Volume metrics (24h, 6h, 1h)
- Liquidity information
- DEX information
```

### 6. Assets
**Files to Add**:
- `surfsense_web/public/connectors/dexscreener.svg` - Connector icon

**Icon Requirements**:
- SVG format
- 24x24px viewBox
- Monochrome design
- Matches SurfSense design system

### 7. Enum Registration
**File**: `surfsense_web/contracts/enums/connector.ts`

**Add to EnumConnectorName**:
```typescript
export enum EnumConnectorName {
  // ... existing connectors
  DEXSCREENER_CONNECTOR = "DEXSCREENER_CONNECTOR",
}
```

## 🔗 Dependencies

### Internal Dependencies
- Story 1.1 (Backend API) - **MUST BE COMPLETED FIRST**
- `@/components/ui/*` - ShadCN UI components
- `@/contracts/enums/connector` - Connector enums
- React Hook Form - Form management
- Zod - Validation schema

### External Dependencies
- None (DexScreener API is public)

## 📊 Data Models

### Token Configuration
```typescript
interface TokenConfig {
  chain: string;          // Blockchain network
  address: string;        // Token contract address (0x...)
  name?: string;          // Optional display name
}
```

### Form Submission
```typescript
interface DexScreenerConnectorSubmission {
  name: string;
  connector_type: "DEXSCREENER_CONNECTOR";
  config: {
    tokens: TokenConfig[];
  };
  is_indexable: true;
  periodic_indexing_enabled: boolean;
  indexing_frequency_minutes: number | null;
  startDate?: Date;
  endDate?: Date;
}
```

## 🧪 Testing Strategy

### Unit Tests
- [ ] Token validation logic
- [ ] Add/remove token functionality
- [ ] Form submission with valid data
- [ ] Form validation with invalid data
- [ ] Chain selector options
- [ ] Token address format validation

### Integration Tests
- [ ] Form submission to backend API
- [ ] Config component updates connector
- [ ] Benefits display correctly
- [ ] Documentation renders properly

### Manual Testing
- [ ] Add connector with single token
- [ ] Add connector with multiple tokens (10+)
- [ ] Edit existing connector
- [ ] Remove tokens from config
- [ ] Test all chain options
- [ ] Verify responsive design
- [ ] Test form validation errors

## 🎨 UI/UX Considerations

### Design Patterns
- Follow Luma connector UI patterns
- Use consistent spacing and typography
- Responsive design for mobile/tablet/desktop
- Clear validation error messages
- Loading states during submission

### User Flow
1. User opens connector popup
2. Selects "DexScreener" from list
3. Enters connector name
4. Adds first token (chain + address)
5. Optionally adds more tokens
6. Configures sync settings
7. Reviews benefits
8. Clicks "Connect"
9. Sees success message

### Error Handling
- Invalid token address format
- Duplicate tokens
- Maximum tokens exceeded (50)
- Network errors during submission
- Backend validation errors

## 📈 Success Metrics

- [ ] User can add DexScreener connector in < 2 minutes
- [ ] Form validation prevents invalid submissions
- [ ] Token management is intuitive
- [ ] Documentation is clear and helpful
- [ ] UI is responsive on all devices

## 🚀 Deployment Plan

### Phase 1: Component Development
1. Create connect form component
2. Create config component
3. Add connector benefits
4. Register in connector registry

### Phase 2: Documentation & Assets
1. Write MDX documentation
2. Add connector icon
3. Update connector list

### Phase 3: Testing & QA
1. Unit tests
2. Integration tests
3. Manual testing
4. Bug fixes

### Phase 4: Release
1. Merge to main branch
2. Deploy to staging
3. Verify functionality
4. Deploy to production

## 📚 Documentation Requirements

- [ ] Component documentation (JSDoc)
- [ ] User guide (MDX)
- [ ] Developer notes for future maintenance
- [ ] Screenshot examples in docs

## 🔒 Security Considerations

- Token addresses validated on frontend
- No sensitive data stored in config
- HTTPS for all API calls
- Input sanitization for token names

## ✅ Definition of Done

- [ ] All acceptance criteria met
- [ ] Components implemented and tested
- [ ] Documentation complete
- [ ] Code reviewed and approved
- [ ] Merged to main branch
- [ ] Deployed to production
- [ ] User can successfully add DexScreener connector
- [ ] Connector appears in connector list
- [ ] Token management works correctly

---

## 📎 Related Files

- Backend Story: [Story 1.1](./story-1.1-dexscreener-connector.md)
- Luma Reference: `surfsense_web/components/assistant-ui/connector-popup/connect-forms/components/luma-connect-form.tsx`
- Connector Docs: `surfsense_web/content/docs/connectors/`

## 💡 Implementation Notes

- DexScreener API is public (no auth required)
- Token addresses must be valid EVM addresses (0x + 40 hex chars)
- Support up to 50 tokens per connector
- Chain list may need updates as new chains are added to DexScreener
- Consider adding token search/autocomplete in future iteration
