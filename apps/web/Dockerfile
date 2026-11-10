# Pramaan web app (Next.js, standalone output). Build context is the REPOSITORY ROOT (pnpm workspace):
#   docker build -f apps/web/Dockerfile -t pramaan-web .
FROM node:22-alpine AS deps
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/ui/package.json packages/ui/
COPY packages/sdk/typescript/package.json packages/sdk/typescript/
RUN pnpm install --frozen-lockfile --filter web...

FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web ./apps/web
COPY packages/ui ./packages/ui
# The browser (not the server) calls the API, so this is the API's address as seen from the user's machine.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter web build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /repo/apps/web/.next/standalone ./
COPY --from=build /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build /repo/apps/web/public ./apps/web/public
RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app
USER app
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --retries=8 CMD wget -qO- http://127.0.0.1:${PORT}/ >/dev/null || exit 1
CMD ["node", "apps/web/server.js"]
