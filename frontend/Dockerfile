# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Next.js `output: "standalone"` (next.config.ts): the runtime stage ships
# only server.js, the pruned node_modules Next traces, static assets and
# public/. Configuration is read per request from process.env, so one image
# serves any instance (ADR-010). Build context: frontend/.

# Digest resolved 2026-10-08 (REQ-BUILD-001, ADR-023).
ARG NODE_IMAGE=node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM ${NODE_IMAGE} AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM ${NODE_IMAGE} AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN addgroup -g 10001 normly && adduser -D -u 10001 -G normly normly
COPY --from=build --chown=normly:normly /app/.next/standalone ./
COPY --from=build --chown=normly:normly /app/.next/static ./.next/static
COPY --from=build --chown=normly:normly /app/public ./public
USER normly
EXPOSE 3000
CMD ["node", "server.js"]
