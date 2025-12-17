# Repository Guidelines

## Project Structure & Module Organization

The repository contains three main modules:
- **`surfsense_web/`**: Next.js 15 frontend with TypeScript
  - `app/`: App router pages and layouts
  - `components/`: React components organized by feature
  - `atoms/`: Jotai atoms for state management
  - `lib/apis/`: API service layer with Zod validation
  - `hooks/`: Custom React hooks (being migrated to jotai+tanstack)
  - `contracts/types/`: Zod schemas and TypeScript types
- **`surfsense_backend/`**: FastAPI Python backend
- **`surfsense_browser_extension/`**: Browser extension

## Build, Test, and Development Commands

**Web Frontend** (from `surfsense_web/`):
```bash
pnpm install        # Install dependencies
pnpm dev           # Start development server
pnpm build         # Production build
pnpm format        # Format code with Biome
```

## Coding Style & Naming Conventions

- **TypeScript**: Use tabs for indentation, arrow functions preferred
- **Files**: kebab-case (e.g., `llm-config-api.service.ts`)
- **Types**: PascalCase with Zod schemas, infer types at end of file
- **Atoms**: Descriptive names with "Atom" suffix (e.g., `documentsAtom`, `createDocumentMutationAtom`)
- **Formatting**: Biome for linting and formatting

## Migration Pattern (Imperative to Jotai+TanStack Query)

When migrating from imperative hooks to jotai+tanstack:
1. Create Zod schemas in `contracts/types/`
2. Create API service in `lib/apis/`
3. Add cache keys to `lib/query-client/cache-keys.ts`
4. Create query/mutation atoms in `atoms/`
5. Replace hook usage in components (maintain backward compatibility)
6. Delete old hook after all usages migrated

**Important**: For queries needing dynamic inputs, use `useQuery` directly in components instead of atoms.

## Commit Guidelines

- **Format**: `type: description` (e.g., `feat: add user API service`, `fix: resolve type error`)
- **Types**: `feat`, `fix`, `refactor`, `docs`, `chore`
- **Scope**: One logical change per commit
- **Build**: Always run `pnpm build` before committing

## Agent-Specific Instructions

- Work incrementally - one function/component at a time
- Never commit without explicit approval
- Remove obvious comments that state what code clearly does
- Follow existing patterns from previous migrations
- Maintain backward compatibility during migrations
