# Portal pages

Six pages, three journeys: a new buyer, an existing hosted user being wound down, and someone without their license file. Items refer to [00d-pivot-plan.md](../00d-pivot-plan.md), Workstream B.

## Who lands where

```mermaid
flowchart LR
    G[Search / social / launch email] --> L["/ landing"]
    L --> D["/downloads"]
    L --> P["/pricing"]
    P -->|Buy| S[Stripe Checkout]
    S -->|paid, redirect| LS["/license/success"]
    P -->|Try free| LI["/license"]
    E[Hosted user: bookmark, login, legacy desktop 0.0.40] --> SU["/sunset"]
    SU --> D
    SU --> P
    M[Lost the file, support email] --> LI
```

| Page | For whom | Reached from | Login | Status |
|---|---|---|---|---|
| `/` landing | new visitors | search, email, social | no | open (B6) |
| `/pricing` | buyers | landing, `/sunset` | no | done |
| `/license/success` | just paid | Stripe redirect only | no | done |
| `/license` | resend, trial | pricing, support, email | no | done |
| `/downloads` | anyone installing | landing, `/sunset`, success page | no | open (B5), may be a landing section |
| `/sunset` | existing hosted users | app redirect, legacy desktop | yes, export needs it | export done; download links, import steps, refund offer open |

## 1. New buyer

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web
    participant St as Stripe
    participant B as Backend
    participant K as Keygen
    U->>W: / landing → /pricing
    U->>St: Buy (Payment Link)
    St->>B: webhook checkout.session.completed
    B->>K: create license, id derived from the session
    B-->>U: email with the license file
    St->>W: redirect /license/success?session_id=…
    W->>B: GET /license/file?session_id=…
    B-->>W: license file
    W-->>U: download the file, where to put it, a copy is in your inbox
    U->>W: /downloads → installer for their OS
```

`/license/success` exists so the buyer never depends on the email arriving. Both paths yield the same file: the Keygen id is derived from the Stripe session, so the webhook and the success page cannot mint two licenses ([01-license-routes.md](01-license-routes.md)).

## 2. Existing hosted user, after T-0

```mermaid
flowchart TD
    A[Opens the web app or legacy desktop 0.0.40] --> H{SUNSET_MODE?}
    H -->|off| DB[Dashboard, unchanged]
    H -->|on| SU["/sunset"]
    SU --> X[1. Export my data, ZIP]
    SU --> D[2. Download the new app]
    SU --> I[3. Import steps]
    SU --> R[4. Refund or discount offer]
    SU --> MCP[5. MCP changes at T+7]
```

Web: `NEXT_PUBLIC_SUNSET_MODE=1` redirects every app route to `/sunset` and lets `ZeroProvider` render without connecting (B4). Legacy desktop 0.0.40 reads `GET /health`, sees `sunset: true`, and opens `/sunset` in its window (contract 4). `/sunset` keeps the login session because export needs it. Every write route answers 410 during the tail, so nothing new is created.

## 3. Without a license file

```mermaid
flowchart LR
    U[User] --> LI["/license"]
    LI -->|resend form| R["POST /license/resend, always 200, files emailed"]
    LI -->|trial form| T["POST /license/trial, 14-day trial file emailed"]
```

No login. Resend always answers 200 so nobody can probe which addresses bought.
