# syntax=docker/dockerfile:1.5
ARG TARGETPLATFORM

# --- Base image with pnpm ---
FROM --platform=${TARGETPLATFORM} node:20-alpine AS base
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@latest --activate

# --- Prod deps stage ---
FROM base AS prod-deps
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.pnpm-store \
    pnpm install --frozen-lockfile --prod

# --- Dev deps / builder stage ---
FROM base AS builder
COPY package.json pnpm-lock.yaml ./
# First copy the config file to avoid fumadocs-mdx postinstall error
COPY source.config.ts ./
COPY content ./content
RUN --mount=type=cache,target=/root/.pnpm-store \
    pnpm install --frozen-lockfile
COPY . .
ARG NEXT_TELEMETRY_DISABLED=1
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm run build

# --- Runtime stage ---
FROM --platform=${TARGETPLATFORM} node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 --ingroup nodejs nextjs

COPY --from=prod-deps /app/node_modules ./node_modules
COPY --from=prod-deps /app/package.json ./package.json
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["pnpm", "start"]