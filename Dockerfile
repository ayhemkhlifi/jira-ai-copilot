# =============================================================================
# Jira AI Copilot — Multi-stage Dockerfile
# =============================================================================
# Stage 1: Build the Vite/React frontend
# Stage 2: Run the FastAPI backend + serve static frontend
# =============================================================================

# --- Stage 1: Build Frontend ---
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Install dependencies first (layer caching)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy frontend source
COPY frontend/ ./

# Pass the production URL to Vite during build
ARG VITE_API_BASE_URL=https://jira-ai-copilot-production.up.railway.app
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build


# --- Stage 2: Python Backend ---
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for HuggingFace models and utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY src/ ./src/
COPY data/ ./data/

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Default environment
ENV PYTHONUNBUFFERED=1
ENV API_PORT=8000
ENV APP_BASE_URL=http://localhost:8000

EXPOSE 8000

# Run the FastAPI server
CMD ["python", "-m", "src.api.server"]
