# Temporal Order Processing System

A fault-tolerant order processing workflow system built with Temporal and Python, demonstrating workflow orchestration, signal handling, and database persistence.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.9+

### Setup
```bash
git clone https://github.com/joeramirez07/temporal-order-system.git
cd temporal-order-system

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker-compose up -d
# Wait 30-60 seconds for services to start
```

### Run
```bash
# Terminal 1: Start workers
python -m src.worker

# Terminal 2: Test workflows
cd scripts
python cli.py start-order test-123
python cli.py approve test-123
python cli.py status test-123
```

## Architecture

**OrderWorkflow (Parent)**
- Receive Order → Validate → Manual Review → Payment → Shipping
- Signals: cancel, approve, update address
- Retry logic for shipping failures

**ShippingWorkflow (Child)**  
- Prepare Package → Dispatch Carrier
- Runs on separate task queue
- Signals parent on dispatch failure

**Database**
- PostgreSQL with orders, payments, events tables
- Idempotent operations using unique keys

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/orders/{id}/start` | Start workflow |
| POST | `/orders/{id}/signals/approve` | Send approval |
| POST | `/orders/{id}/signals/cancel` | Cancel order |
| GET | `/orders/{id}/status` | Get status |

Start API server: `uvicorn src.api:app --port 8000`

## Testing

```bash
# Run test suite
pytest tests/

# Basic functionality
python test_basic.py

# Database verification
python check_status.py

# 15-second completion demo
python fast_demo.py
```

## Key Features

- Parent-child workflow relationships
- Idempotent payment processing
- Signal-based manual approval
- Comprehensive retry policies
- Database audit trails
- REST API and CLI interfaces
- Fault tolerance with flaky_call() simulation

## Project Structure
```
src/
├── workflows.py          # Workflow definitions
├── activities.py         # Temporal activities  
├── business_functions.py # Business logic
├── database.py          # Database operations
├── worker.py            # Temporal workers
└── api.py               # REST API

scripts/cli.py           # Command line interface
tests/test_workflows.py  # Test suite
docker-compose.yml       # Infrastructure
```

## Technical Decisions

**Idempotency**: Payment operations use unique payment_id as primary key with conflict handling

**Task Queues**: Separate queues (main-tq, shipping-tq) enable independent scaling

**Error Handling**: Exponential backoff retries with maximum 3 attempts per activity

**Parent-Child Communication**: Child workflows signal parent on failures for retry coordination

**15-Second Constraint**: Achievable when business logic succeeds; flaky_call() simulates real-world delays

## Monitoring

- Temporal Web UI: http://localhost:8233
- API docs: http://localhost:8000/docs  
- Database status: `python check_status.py`
- Structured logging for all operations

The system handles the complete order lifecycle with proper fault tolerance, state persistence, and observability required for production workflow orchestration.