FROM node:24-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20
WORKDIR /repo
RUN npm install --global pnpm@11.7.0
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages/protocol packages/protocol
COPY packages/terralex packages/terralex
COPY services/oracle services/oracle
COPY policies policies
COPY services/autonomy/fixture-server.ts services/autonomy/fixture-server.ts
RUN pnpm install --frozen-lockfile && pnpm --filter @terravoce/protocol build && pnpm --filter @terravoce/terralex build && pnpm --filter @terravoce/oracle build
CMD ["pnpm", "exec", "tsx", "services/autonomy/fixture-server.ts"]
