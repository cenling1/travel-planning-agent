# ============================================================
# Dockerfile — Multi-stage build for Vue 3 Production
# Stage 1: Build the Vue app
# Stage 2: Serve with Nginx
# ============================================================

# ---- Build Stage ----
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (layer caching)
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

# Copy source and build
COPY . .
RUN npm run build

# ---- Production Stage ----
FROM nginx:alpine

ARG NGINX_CONFIG=nginx/default.conf

# Remove default Nginx config
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy custom Nginx config
COPY ${NGINX_CONFIG} /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/health || exit 1

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
