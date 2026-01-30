# Use a slim Python 3.11 image for a smaller footprint
FROM python:3.11-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Install system dependencies, including git
# Using apt-get for Debian-based slim-buster
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Copy only necessary project files for dependency installation
# This helps leverage Docker's build cache
COPY pyproject.toml uv.lock ./
COPY src/kotic_cli ./src/kotic_cli

# Install dependencies using uv
# [server] installs optional dependencies for the FastAPI server
RUN uv sync --extra server

# Expose the port FastAPI will run on
EXPOSE 8000

# Command to run the FastAPI application using uvicorn
# --host 0.0.0.0 makes it accessible from outside the container
# --port 8000 specifies the port
# --factory allows loading the FastAPI app without needing an extra file
CMD ["uv", "run", "uvicorn", "src.kotic_cli.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"]
