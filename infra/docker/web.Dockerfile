# Next.js UI. API_URL is baked in at build time (Next writes rewrites into its routes manifest),
# so the compose build passes the API's in-network address.
FROM node:22-slim AS build
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY apps/web ./
ARG API_URL=http://api:8000
ENV API_URL=$API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build && npm prune --omit=dev

FROM node:22-slim
WORKDIR /web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build --chown=node /web/package.json /web/next.config.ts ./
COPY --from=build --chown=node /web/node_modules node_modules
COPY --from=build --chown=node /web/.next .next
COPY --from=build --chown=node /web/public public
USER node
EXPOSE 3000
CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
