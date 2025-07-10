# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including devDependencies needed for build)
RUN npm ci

# Copy all source files (the build context should be the frontend directory)
COPY . .

# Ensure src/lib directory exists and has utils.ts
RUN mkdir -p src/lib

# Create utils.ts if it doesn't exist (fallback)
RUN if [ ! -f "src/lib/utils.ts" ]; then \
    echo 'import { type ClassValue, clsx } from "clsx"; \
import { twMerge } from "tailwind-merge"; \
\
export function cn(...inputs: ClassValue[]) { \
  return twMerge(clsx(inputs)); \
}' > src/lib/utils.ts; \
    echo "WARNING: Created src/lib/utils.ts as it was missing"; \
    fi

# Debug: List files to ensure they're copied correctly
RUN ls -la
RUN ls -la src/ || echo "src directory not found"
RUN ls -la src/lib/ || echo "src/lib directory not found"
RUN cat src/lib/utils.ts || echo "utils.ts content not readable"
RUN if [ -d "public" ]; then ls -la public/; else echo "public directory not found, creating it"; mkdir -p public; fi

# Create index.html if it doesn't exist
RUN if [ ! -f "public/index.html" ]; then \
    echo '<!DOCTYPE html><html><head><meta charset="utf-8"><title>React App</title></head><body><div id="root"></div></body></html>' > public/index.html; \
    fi

# Build the application
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build:verbose

# Production stage
FROM nginx:alpine

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built application from builder stage
COPY --from=builder /app/build /usr/share/nginx/html

# Create non-root user
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /usr/share/nginx/html && \
    chown -R appuser:appuser /var/cache/nginx && \
    chown -R appuser:appuser /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R appuser:appuser /var/run/nginx.pid

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80 || exit 1

CMD ["nginx", "-g", "daemon off;"]