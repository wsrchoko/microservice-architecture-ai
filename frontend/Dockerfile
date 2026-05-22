FROM node:20-alpine AS base

FROM base AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ARG AUTH_SERVICE_URL=http://auth-service:8001
ARG USER_SERVICE_URL=http://user-service:8002
ARG ROLE_SERVICE_URL=http://role-service:8003
ARG AUDIT_SERVICE_URL=http://audit-service:8004
ARG AI_SERVICE_URL=http://ai-service:8005

ENV AUTH_SERVICE_URL=$AUTH_SERVICE_URL
ENV USER_SERVICE_URL=$USER_SERVICE_URL
ENV ROLE_SERVICE_URL=$ROLE_SERVICE_URL
ENV AUDIT_SERVICE_URL=$AUDIT_SERVICE_URL
ENV AI_SERVICE_URL=$AI_SERVICE_URL

RUN npm run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]