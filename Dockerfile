FROM python:3.11 AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create a virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Second stage: final image
FROM python:3.11

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create necessary directories for data persistence
RUN mkdir -p /app/output /app/analysis_cache /app/transcript_cache

# Expose the port Streamlit runs on
EXPOSE 8501

# Set environment variable to ensure Streamlit runs correctly in Docker
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Docker-specific YouTube API configuration to avoid blocking
ENV ENVIRONMENT=development
ENV YOUTUBE_ANALYSIS_DISABLE_SSL_VERIFY=1
ENV YOUTUBE_HTTP_USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
ENV YOUTUBE_HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9"
ENV PYTHONHTTPSVERIFY=0

# Command to run the application (updated path to reflect refactored structure)
CMD ["streamlit", "run", "src/youtube_analysis_webapp.py", "--server.port=8501", "--server.address=0.0.0.0"] 
