FROM node:24-alpine AS build

WORKDIR /app

ARG VITE_API_ORIGIN=http://127.0.0.1:6687
ENV VITE_API_ORIGIN=$VITE_API_ORIGIN

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN corepack enable && pnpm install --frozen-lockfile

COPY apps/web apps/web
RUN pnpm --dir apps/web build

FROM nginx:alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 6688

CMD ["nginx", "-g", "daemon off;"]
