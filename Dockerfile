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
RUN mkdir -p /app/output /app/db

# Expose the port Streamlit runs on
EXPOSE 8501

# Set environment variable to ensure Streamlit runs correctly in Docker
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Command to run the application
CMD ["streamlit", "run", "youtube_analysis_webapp.py", "--server.port=8501", "--server.address=0.0.0.0"] 
