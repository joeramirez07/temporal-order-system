# Temporal Order Processing System

A fault-tolerant order processing workflow system built with [Temporal](https://temporal.io/) and Python, demonstrating complex workflow orchestration with parent-child relationships, signal handling, and database persistence.

## Architecture Overview

- **OrderWorkflow** (Parent): Orchestrates the complete order lifecycle
- **ShippingWorkflow** (Child): Handles package preparation and carrier dispatch
- **Separate Task Queues**: `main-tq` for order processing, `shipping-tq` for shipping operations
- **PostgreSQL Database**: Persistent storage with idempotent operations
- **Docker Compose**: Complete local development environment

## Features

- ✅ Parent-child workflow relationships
- ✅ Signal-based manual approval process
- ✅ Idempotent payment processing
- ✅ Comprehensive retry policies and error handling
- ✅ Database persistence with audit trails
- ✅ CLI interface for workflow management
- ✅ Fault tolerance testing with `flaky_call()` simulation

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.9+

### Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd temporal-order-system

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start services
docker-compose up -d

# Wait for services to initialize (30-60 seconds)