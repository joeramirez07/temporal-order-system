import asyncio
import random
import json
import logging
from datetime import datetime
from typing import Dict, Any
from .database import get_db_pool

logger = logging.getLogger(__name__)

# =============================================================================
# REQUIRED HELPER FUNCTION (Cannot be changed per assignment)
# =============================================================================

async def flaky_call() -> None:
    """Either raise an error or sleep long enough to trigger an activity timeout."""
    rand_num = random.random()
    if rand_num < 0.33:
        raise RuntimeError("Forced failure for testing")
    if rand_num < 0.67:
        await asyncio.sleep(300)  # Expect the activity layer to time out before this completes

# =============================================================================
# BUSINESS LOGIC FUNCTIONS (Call flaky_call, implement DB operations)
# =============================================================================

async def order_received(order_id: str) -> Dict[str, Any]:
    """Receive and store an order"""
    await flaky_call()
    
    # DB write: insert new order record
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO orders (id, state, items_json, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $4)
            ON CONFLICT (id) DO NOTHING
            """,
            order_id, "received", json.dumps([{"sku": "ABC", "qty": 1}]), datetime.utcnow()
        )
    
    logger.info(f"Order {order_id} received and stored in DB")
    return {"order_id": order_id, "items": [{"sku": "ABC", "qty": 1}]}

async def order_validated(order: Dict[str, Any]) -> bool:
    """Validate an order"""
    await flaky_call()
    
    order_id = order["order_id"]
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        # Check if order exists
        row = await conn.fetchrow("SELECT * FROM orders WHERE id = $1", order_id)
        if not row:
            raise ValueError(f"Order {order_id} not found")
        
        if not order.get("items"):
            raise ValueError("No items to validate")
        
        # Update validation status
        await conn.execute(
            "UPDATE orders SET state = $1, updated_at = $2 WHERE id = $3",
            "validated", datetime.utcnow(), order_id
        )
    
    logger.info(f"Order {order_id} validated")
    return True

async def payment_charged(order: Dict[str, Any], payment_id: str) -> Dict[str, Any]:
    """Charge payment with idempotency logic"""
    await flaky_call()
    
    order_id = order["order_id"]
    amount = sum(i.get("qty", 1) for i in order.get("items", []))
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Idempotency check - use payment_id as unique key
        existing = await conn.fetchrow(
            "SELECT * FROM payments WHERE payment_id = $1", payment_id
        )
        
        if existing:
            logger.info(f"Payment {payment_id} already processed (idempotent)")
            return {"status": "charged", "amount": existing["amount"], "payment_id": payment_id}
        
        # Insert new payment record
        await conn.execute(
            """
            INSERT INTO payments (payment_id, order_id, status, amount, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            payment_id, order_id, "charged", amount, datetime.utcnow()
        )
        
        # Update order status
        await conn.execute(
            "UPDATE orders SET state = $1, updated_at = $2 WHERE id = $3",
            "payment_charged", datetime.utcnow(), order_id
        )
    
    logger.info(f"Payment {payment_id} charged for order {order_id}, amount: {amount}")
    return {"status": "charged", "amount": amount, "payment_id": payment_id}

async def package_prepared(order: Dict[str, Any]) -> str:
    """Prepare package for shipping"""
    await flaky_call()
    
    order_id = order["order_id"]
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET state = $1, updated_at = $2 WHERE id = $3",
            "package_prepared", datetime.utcnow(), order_id
        )
        
        # Log event
        await conn.execute(
            """
            INSERT INTO events (order_id, type, payload_json, ts)
            VALUES ($1, $2, $3, $4)
            """,
            order_id, "package_prepared", json.dumps({}), datetime.utcnow()
        )
    
    logger.info(f"Package prepared for order {order_id}")
    return "Package ready"

async def carrier_dispatched(order: Dict[str, Any]) -> str:
    """Dispatch carrier for delivery"""
    await flaky_call()
    
    order_id = order["order_id"]
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET state = $1, updated_at = $2 WHERE id = $3",
            "dispatched", datetime.utcnow(), order_id
        )
        
        # Log event
        await conn.execute(
            """
            INSERT INTO events (order_id, type, payload_json, ts)
            VALUES ($1, $2, $3, $4)
            """,
            order_id, "carrier_dispatched", json.dumps({}), datetime.utcnow()
        )
    
    logger.info(f"Carrier dispatched for order {order_id}")
    return "Dispatched"