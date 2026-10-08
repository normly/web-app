# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 normly contributors
#
# Next.js `output: "standalone"` (next.config.ts): the runtime stage ships
# only server.js, the pruned node_modules Next traces, static assets and
# public/. Configuration is read per request from process.env, so one image
# serves any instance (ADR-010). Build context: frontend/.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
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
