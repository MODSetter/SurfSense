# Pact.js Utils Consumer Helpers

## Principle

Use `createProviderState`, `toJsonMap`, `setJsonContent`, and `setJsonBody` from `@seontechnologies/pactjs-utils` to build type-safe provider state tuples and reusable PactV4 JSON callbacks for consumer contract tests. These helpers eliminate manual `JsonMap` casting and repetitive inline builder lambdas.

## Rationale

### Problems with raw consumer helper handling

- **JsonMap requirement**: Pact's `.given(stateName, params)` requires `params` to be `JsonMap` — a flat object where every value must be `string | number | boolean | null`
- **Type gymnastics**: Complex params (Date objects, nested objects, null values) require manual casting that TypeScript can't verify
- **Inconsistent serialization**: Different developers serialize the same data differently (e.g., dates as ISO strings vs timestamps)
- **Verbose `.given()` calls**: Repeating state name and params inline makes consumer tests harder to read
- **Repeated interaction callbacks**: PactV4 interactions duplicate inline `(builder) => { ... }` blocks for body/query/header setup

### Solutions

- **`createProviderState`**: Returns a `[string, JsonMap]` tuple that spreads directly into `.given()` — one function handles name and params
- **`toJsonMap`**: Explicit coercion rules documented and tested — Date→ISO string, null→"null" string, nested objects→JSON string
- **`setJsonContent`**: Curried callback helper for request/response builders — set `query`, `headers`, and/or `body` from one reusable function
- **`setJsonBody`**: Body-only shorthand for `setJsonContent({ body })` — ideal for concise `.willRespondWith(...)` bodies

## Pattern Examples

### Example 1: Basic Provider State Creation

```typescript
import { PactV3, MatchersV3 } from '@pact-foundation/pact';
import { createProviderState } from '@seontechnologies/pactjs-utils';

const provider = new PactV3({
  consumer: 'movie-web',
  provider: 'SampleMoviesAPI',
  dir: './pacts',
});

describe('Movie API Contract', () => {
  it('should return movie by id', async () => {
    // createProviderState returns [stateName, JsonMap] tuple
    const providerState = createProviderState({
      name: 'movie with id 1 exists',
      params: { id: 1, name: 'Inception', year: 2010 },
    });

    await provider
      .given(...providerState) // Spread tuple into .given(name, params)
      .uponReceiving('a request for movie 1')
      .withRequest({ method: 'GET', path: '/movies/1' })
      .willRespondWith({
        status: 200,
        body: MatchersV3.like({ id: 1, name: 'Inception', year: 2010 }),
      })
      .executeTest(async (mockServer) => {
        const res = await fetch(`${mockServer.url}/movies/1`);
        const movie = await res.json();
        expect(movie.name).toBe('Inception');
      });
  });
});
```

**Key Points**:

- `createProviderState` accepts `{ name: string, params: Record<string, unknown> }`
- Both `name` and `params` are required (pass `params: {}` for states without parameters)
- Returns `[string, JsonMap]` — spread with `...` into `.given()`
- `params` values are automatically converted to JsonMap-compatible types
- Works identically with HTTP (`PactV3`) and message (`MessageConsumerPact`) pacts

### Example 2: Complex Parameters with toJsonMap

```typescript
import { toJsonMap } from '@seontechnologies/pactjs-utils';

// toJsonMap conversion rules:
// - string, number, boolean → passed through
// - null → "null" (string)
// - undefined → "null" (string, same as null)
// - Date → ISO string (e.g., "2025-01-15T10:00:00.000Z")
// - nested object → JSON string
// - array → comma-separated string via String() (e.g., [1,2,3] → "1,2,3")

const params = toJsonMap({
  id: 42,
  name: 'John Doe',
  active: true,
  score: null,
  createdAt: new Date('2025-01-15T10:00:00Z'),
  metadata: { role: 'admin', permissions: ['read', 'write'] },
});

// Result:
// {
//   id: 42,
//   name: "John Doe",
//   active: true,
//   score: "null",
//   createdAt: "2025-01-15T10:00:00.000Z",
//   metadata: '{"role":"admin","permissions":["read","write"]}'
// }
```

**Key Points**:

- `toJsonMap` is called internally by `createProviderState` — you rarely need it directly
- Use it when you need explicit control over parameter conversion outside of provider states
- Conversion rules are deterministic: same input always produces same output

### Example 3: Provider State Without Parameters

```typescript
import { createProviderState } from '@seontechnologies/pactjs-utils';

// State without params — second tuple element is empty object
const emptyState = createProviderState({ name: 'no movies exist', params: {} });
// Returns: ['no movies exist', {}]

await provider
  .given(...emptyState)
  .uponReceiving('a request when no movies exist')
  .withRequest({ method: 'GET', path: '/movies' })
  .willRespondWith({ status: 200, body: [] })
  .executeTest(async (mockServer) => {
    const res = await fetch(`${mockServer.url}/movies`);
    const movies = await res.json();
    expect(movies).toEqual([]);
  });
```

### Example 4: Multiple Provider States

```typescript
import { createProviderState } from '@seontechnologies/pactjs-utils';

// Some interactions require multiple provider states
// Call .given() multiple times with different states
await provider
  .given(...createProviderState({ name: 'user is authenticated', params: { userId: 1 } }))
  .given(...createProviderState({ name: 'movie with id 5 exists', params: { id: 5 } }))
  .uponReceiving('an authenticated request for movie 5')
  .withRequest({
    method: 'GET',
    path: '/movies/5',
    headers: { Authorization: MatchersV3.like('Bearer token') },
  })
  .willRespondWith({ status: 200, body: MatchersV3.like({ id: 5 }) })
  .executeTest(async (mockServer) => {
    // test implementation
  });
```

### Example 5: When to Use setJsonBody vs setJsonContent

```typescript
import { MatchersV3 } from '@pact-foundation/pact';
import { setJsonBody, setJsonContent } from '@seontechnologies/pactjs-utils';

const { integer, string } = MatchersV3;

await pact
  .addInteraction()
  .given('movie exists')
  .uponReceiving('a request to get movie by name')
  .withRequest(
    'GET',
    '/movies',
    setJsonContent({
      query: { name: 'Inception' },
      headers: { Accept: 'application/json' },
    }),
  )
  .willRespondWith(
    200,
    setJsonBody({
      status: 200,
      data: { id: integer(1), name: string('Inception') },
    }),
  );
```

**Key Points**:

- Use `setJsonContent` when the interaction needs `query`, `headers`, and/or `body` in one callback (most request builders)
- Use `setJsonBody` when you only need `jsonBody` and want the shorter `.willRespondWith(status, setJsonBody(...))` form
- `setJsonBody` is equivalent to `setJsonContent({ body: ... })`

## Key Points

- **Spread pattern**: Always use `...createProviderState()` — the tuple spreads into `.given(stateName, params)`
- **Type safety**: TypeScript enforces `{ name: string, params: Record<string, unknown> }` input (both fields required)
- **Null handling**: `null` becomes `"null"` string in JsonMap (Pact requirement)
- **Date handling**: Date objects become ISO 8601 strings
- **No nested objects in JsonMap**: Nested objects are JSON-stringified — provider state handlers must parse them
- **Array serialization is lossy**: Arrays are converted via `String()` (e.g., `[1,2,3]` → `"1,2,3"`) — prefer passing arrays as JSON-stringified objects for round-trip safety
- **Message pacts**: Works identically with `MessageConsumerPact` — same `.given()` API
- **Builder reuse**: `setJsonContent` works for both `.withRequest(...)` and `.willRespondWith(...)` callbacks (query is ignored on response builders)
- **Body shorthand**: `setJsonBody` keeps body-only responses concise and readable
- **Matchers check type, not value**: `string('My movie')` means "any string", `integer(1)` means "any integer". The example values are arbitrary — the provider can return different values and verification still passes as long as the type matches. Use matchers only in `.willRespondWith()` (responses), never in `.withRequest()` (requests) — Postel's Law applies.
- **Reuse test values across files**: Interactions are uniquely identified by `uponReceiving` + `.given()`, not by placeholder values. Two test files can both use `testId: 100` without conflicting. On the provider side, shared values simplify state handlers — idempotent handlers (check if exists, create if not) only need to ensure one record exists. Use different values only when testing different states of the same entity type (e.g., `movieExists(100)` for happy paths vs. `movieNotFound(999)` for error paths).

## Related Fragments

- `pactjs-utils-overview.md` — installation, decision tree, design philosophy
- `pactjs-utils-provider-verifier.md` — provider-side state handler implementation
- `contract-testing.md` — foundational patterns with raw Pact.js

## Anti-Patterns

### Wrong: Manual JsonMap assembly

```typescript
// ❌ Manual casting — verbose, error-prone, no type safety
provider.given('user exists', {
  id: 1 as unknown as string,
  createdAt: new Date().toISOString(),
  metadata: JSON.stringify({ role: 'admin' }),
} as JsonMap);
```

### Right: Use createProviderState

```typescript
// ✅ Automatic conversion with type safety
provider.given(
  ...createProviderState({
    name: 'user exists',
    params: { id: 1, createdAt: new Date(), metadata: { role: 'admin' } },
  }),
);
```

### Wrong: Inline state names without helper

```typescript
// ❌ Duplicated state names between consumer and provider — easy to mismatch
provider.given('a user with id 1 exists', { id: '1' });
// Later in provider: 'user with id 1 exists' — different string!
```

### Right: Share state constants

```typescript
// ✅ Define state names as constants shared between consumer and provider
const STATES = {
  USER_EXISTS: 'user with id exists',
  NO_USERS: 'no users exist',
} as const;

provider.given(...createProviderState({ name: STATES.USER_EXISTS, params: { id: 1 } }));
```

### Wrong: Repeating inline builder lambdas everywhere

```typescript
// ❌ Repetitive callback boilerplate in every interaction
.willRespondWith(200, (builder) => {
  builder.jsonBody({ status: 200 });
});
```

### Right: Use setJsonBody / setJsonContent

```typescript
// ✅ Reusable callbacks with less boilerplate
.withRequest('GET', '/movies', setJsonContent({ query: { name: 'Inception' } }))
.willRespondWith(200, setJsonBody({ status: 200 }));
```

_Source: @seontechnologies/pactjs-utils consumer-helpers module, pactjs-utils sample-app consumer tests_
