# node:22 satisfies this project's Vite/rolldown engine requirement
# (^20.19.0 || >=22.12.0) — see docs/openapi/README.md-adjacent notes in the
# frontend scaffold about the local dev machine needing the same upgrade.
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
