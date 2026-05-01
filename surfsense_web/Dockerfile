# syntax=docker.io/docker/dockerfile:1

FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
# Check https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine to understand why libc6-compat might be needed.
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Install pnpm
RUN corepack enable pnpm

# Copy package files
COPY package.json pnpm-lock.yaml* .npmrc* ./

# First copy the config file and content to avoid fumadocs-mdx postinstall error
COPY source.config.ts ./
COPY content ./content

# Install dependencies with frozen lockfile
RUN pnpm i --frozen-lockfile


# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app

# Enable pnpm
RUN corepack enable pnpm

# Build with placeholder values for NEXT_PUBLIC_* variables.
# These are replaced at container startup by docker-entrypoint.js
# with real values from the container's environment variables.
ARG NEXT_PUBLIC_FASTAPI_BACKEND_URL=__NEXT_PUBLIC_FASTAPI_BACKEND_URL__
ARG NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE=__NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE__
ARG NEXT_PUBLIC_ETL_SERVICE=__NEXT_PUBLIC_ETL_SERVICE__
ARG NEXT_PUBLIC_ZERO_CACHE_URL=__NEXT_PUBLIC_ZERO_CACHE_URL__
ARG NEXT_PUBLIC_DEPLOYMENT_MODE=__NEXT_PUBLIC_DEPLOYMENT_MODE__
ARG NEXT_PUBLIC_OAUTH2_PROXY_URL=__NEXT_PUBLIC_OAUTH2_PROXY_URL__
# These are baked at build time (not placeholder-substituted). Next.js inlines
# them as literal strings and terser dead-code-eliminates branches based on
# truthiness; placeholder tokens look truthy and defeat that optimization.
ARG NEXT_PUBLIC_LOGOUT_REDIRECT_URL=
ARG NEXT_PUBLIC_OIDC_LOGOUT_URL=
ARG NEXT_PUBLIC_OIDC_CLIENT_ID=
ARG NEXT_PUBLIC_SMB_NAME=__NEXT_PUBLIC_SMB_NAME__

ENV NEXT_PUBLIC_FASTAPI_BACKEND_URL=$NEXT_PUBLIC_FASTAPI_BACKEND_URL
ENV NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE=$NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE
ENV NEXT_PUBLIC_ETL_SERVICE=$NEXT_PUBLIC_ETL_SERVICE
ENV NEXT_PUBLIC_ZERO_CACHE_URL=$NEXT_PUBLIC_ZERO_CACHE_URL
ENV NEXT_PUBLIC_DEPLOYMENT_MODE=$NEXT_PUBLIC_DEPLOYMENT_MODE
ENV NEXT_PUBLIC_OAUTH2_PROXY_URL=$NEXT_PUBLIC_OAUTH2_PROXY_URL
ENV NEXT_PUBLIC_LOGOUT_REDIRECT_URL=$NEXT_PUBLIC_LOGOUT_REDIRECT_URL
ENV NEXT_PUBLIC_OIDC_LOGOUT_URL=$NEXT_PUBLIC_OIDC_LOGOUT_URL
ENV NEXT_PUBLIC_OIDC_CLIENT_ID=$NEXT_PUBLIC_OIDC_CLIENT_ID
ENV NEXT_PUBLIC_SMB_NAME=$NEXT_PUBLIC_SMB_NAME

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Next.js collects completely anonymous telemetry data about general usage.
# Learn more here: https://nextjs.org/telemetry
# Uncomment the following line in case you want to disable telemetry during the build.
# ENV NEXT_TELEMETRY_DISABLED=1

RUN pnpm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
# Uncomment the following line in case you want to disable telemetry during runtime.
# ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Automatically leverage output traces to reduce image size
# https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone/app/ ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Entrypoint scripts for runtime env var substitution
COPY --chown=nextjs:nodejs docker-entrypoint.js ./docker-entrypoint.js
COPY --chown=nextjs:nodejs --chmod=755 docker-entrypoint.sh ./docker-entrypoint.sh

USER nextjs

EXPOSE 3000

ENV PORT=3000

# server.js is created by next build from the standalone output
# https://nextjs.org/docs/pages/api-reference/config/next-config-js/output
ENV HOSTNAME="0.0.0.0"
ENTRYPOINT ["/bin/sh", "./docker-entrypoint.sh"]