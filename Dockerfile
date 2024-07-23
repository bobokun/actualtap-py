# Use Python 3.12 Alpine as the base image
FROM python:3.12-alpine

# Set up build argument and environment variable for branch name
ARG BRANCH_NAME=main
ENV BRANCH_NAME=${BRANCH_NAME}

# Set the Tini version
ENV TINI_VERSION=v0.19.0

# Set up build argument and environment variable for config directory
ARG CONFIG_DIR=/config
ENV CONFIG_DIR=/config

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt /

# Install necessary system dependencies and Tini
RUN apk add --no-cache gcc musl-dev libffi-dev tini

# Copy the rest of the application code into the container
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade -r /requirements.txt && pip install -e .

# Create a volume for the config directory
VOLUME /config

# Expose port 8000 for the FastAPI application
EXPOSE 8000

# Set the entrypoint to run the application using Tini as the init process
ENTRYPOINT ["/sbin/tini", "-s", "--", "/app/copy-config.sh", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
