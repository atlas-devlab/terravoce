FROM node:24-bookworm-slim AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages ./packages
COPY services/oracle ./services/oracle
COPY policies ./policies
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @terravoce/protocol build \
 && pnpm --filter @terravoce/terralex build \
 && pnpm --filter @terravoce/oracle build
RUN pnpm --filter @terravoce/oracle deploy --prod /prod/oracle

FROM node:24-bookworm-slim
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /prod/oracle ./
COPY --from=build /app/policies ./policies
EXPOSE 8787
CMD ["node", "dist/server.js"]
