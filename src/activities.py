import logging
from datetime import timedelta
from typing import Dict, Any
from temporalio import activity
from temporalio.common import RetryPolicy

from .business_functions import (
    order_received,
    order_validated,
    payment_charged,
    package_prepared,
    carrier_dispatched
)

logger = logging.getLogger(__name__)

# =============================================================================
# TEMPORAL ACTIVITIES
# =============================================================================

@activity.defn
async def receive_order_activity(order_id: str) -> Dict[str, Any]:
    """Activity to receive and store an order"""
    logger.info(f"Processing order reception for {order_id}")
    try:
        result = await order_received(order_id)
        logger.info(f"Order {order_id} received successfully")
        return result
    except Exception as e:
        logger.error(f"Failed to receive order {order_id}: {e}")
        raise

@activity.defn  
async def validate_order_activity(order: Dict[str, Any]) -> bool:
    """Activity to validate an order"""
    order_id = order.get("order_id", "unknown")
    logger.info(f"Validating order {order_id}")
    try:
        result = await order_validated(order)
        logger.info(f"Order {order_id} validated successfully")
        return result
    except Exception as e:
        logger.error(f"Failed to validate order {order_id}: {e}")
        raise

@activity.defn
async def charge_payment_activity(order: Dict[str, Any], payment_id: str) -> Dict[str, Any]:
    """Activity to charge payment with idempotency"""
    order_id = order.get("order_id", "unknown")
    logger.info(f"Charging payment {payment_id} for order {order_id}")
    try:
        result = await payment_charged(order, payment_id)
        logger.info(f"Payment {payment_id} charged successfully for order {order_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to charge payment {payment_id} for order {order_id}: {e}")
        raise

@activity.defn
async def prepare_package_activity(order: Dict[str, Any]) -> str:
    """Activity to prepare package"""
    order_id = order.get("order_id", "unknown")
    logger.info(f"Preparing package for order {order_id}")
    try:
        result = await package_prepared(order)
        logger.info(f"Package prepared successfully for order {order_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to prepare package for order {order_id}: {e}")
        raise

@activity.defn
async def dispatch_carrier_activity(order: Dict[str, Any]) -> str:
    """Activity to dispatch carrier"""
    order_id = order.get("order_id", "unknown")
    logger.info(f"Dispatching carrier for order {order_id}")
    try:
        result = await carrier_dispatched(order)
        logger.info(f"Carrier dispatched successfully for order {order_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to dispatch carrier for order {order_id}: {e}")
        raise

# Activity configurations
ACTIVITY_CONFIG = {
    "start_to_close_timeout": timedelta(seconds=10),
    "retry_policy": RetryPolicy(
        initial_interval=timedelta(seconds=1),
        maximum_interval=timedelta(seconds=30),
        maximum_attempts=3,
        backoff_coefficient=2.0
    )
}