FROM node:24-alpine AS build

WORKDIR /app

ARG VITE_LIVE_POSITION_WINDOW_MINUTES=10
ENV VITE_LIVE_POSITION_WINDOW_MINUTES=$VITE_LIVE_POSITION_WINDOW_MINUTES

COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci

COPY frontend/ .

RUN npm run build

FROM nginx:1.29-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
