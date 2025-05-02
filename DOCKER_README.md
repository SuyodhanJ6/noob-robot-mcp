# Docker Setup for Robot Framework MCP Server

This document provides instructions for building and running the Robot Framework MCP Server in Docker.

## Prerequisites

- Docker installed on your system
- Docker Compose (optional, for easier deployment)

## Building the Docker Image

You can build the Docker image using the following command:

```bash
docker build -t robot-mcp-server .
```

This will create a Docker image named `robot-mcp-server` based on the Dockerfile in the current directory.

## Running the Container

### Using Docker

To run the container directly with Docker:

```bash
docker run -p 3007:3007 \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=3007 \
  -e ALLOWED_ORIGINS="*" \
  robot-mcp-server
```

### Using Docker Compose

For easier deployment, you can use Docker Compose:

```bash
docker-compose up -d
```

This will start the service in detached mode. To view logs:

```bash
docker-compose logs -f
```

To stop the service:

```bash
docker-compose down
```

## Configuration

The Docker container can be configured using the following environment variables:

- `MCP_HOST`: The host to bind the server to (default: 0.0.0.0)
- `MCP_PORT`: The port to run the server on (default: 3007)
- `ALLOWED_ORIGINS`: Comma-separated list of allowed origins for CORS (default: *)

## Data Storage

All data, including logs, output files, and screenshots, are stored inside the container in the following directories:

- `/app/logs`: Server logs
- `/app/output`: Robot Framework output files 
- `/app/reports`: Robot Framework reports and screenshots

Note: Since the data is stored inside the container, it will be lost when the container is removed. If you need to persist this data, you can use Docker volumes or bind mounts.

## Health Check

The Docker container includes a health check that pings the server to ensure it's running properly. You can check the health status with:

```bash
docker ps
```

The health status will be displayed in the output. 