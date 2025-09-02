import logging
from datetime import timedelta
from typing import Dict, Any, Optional
from temporalio import workflow
from temporalio.exceptions import TimeoutError

from .activities import (
    receive_order_activity,
    validate_order_activity,
    charge_payment_activity,
    prepare_package_activity,
    dispatch_carrier_activity,
    ACTIVITY_CONFIG
)

logger = logging.getLogger(__name__)

# =============================================================================
# SHIPPING WORKFLOW (Child)
# =============================================================================

@workflow.defn
class ShippingWorkflow:
    def __init__(self) -> None:
        self._order: Optional[Dict[str, Any]] = None

    @workflow.run
    async def run(self, order: Dict[str, Any]) -> str:
        """Run the shipping workflow"""
        self._order = order
        order_id = order.get("order_id", "unknown")
        
        logger.info(f"Starting shipping workflow for order {order_id}")
        
        try:
            # Step 1: Prepare package
            logger.info(f"Preparing package for order {order_id}")
            await workflow.execute_activity(
                prepare_package_activity,
                order,
                **ACTIVITY_CONFIG
            )
            
            # Step 2: Dispatch carrier
            logger.info(f"Dispatching carrier for order {order_id}")
            result = await workflow.execute_activity(
                dispatch_carrier_activity,
                order,
                **ACTIVITY_CONFIG
            )
            
            logger.info(f"Shipping completed for order {order_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Shipping failed for order {order_id}: {e}")
            # In a real implementation, we'd signal the parent workflow here
            raise

# =============================================================================
# ORDER WORKFLOW (Parent)
# =============================================================================

@workflow.defn
class OrderWorkflow:
    def __init__(self) -> None:
        self._order: Optional[Dict[str, Any]] = None
        self._cancelled = False
        self._manual_approval_received = False
        self._address_updated = False

    @workflow.run
    async def run(self, order_id: str, payment_id: str) -> str:
        """Run the complete order workflow"""
        logger.info(f"Starting order workflow for {order_id} with payment {payment_id}")
        
        try:
            # Step 1: Receive Order
            logger.info(f"Step 1: Receiving order {order_id}")
            self._order = await workflow.execute_activity(
                receive_order_activity,
                order_id,
                **ACTIVITY_CONFIG
            )
            
            if self._cancelled:
                logger.info(f"Order {order_id} cancelled after reception")
                return "Order cancelled"
            
            # Step 2: Validate Order
            logger.info(f"Step 2: Validating order {order_id}")
            await workflow.execute_activity(
                validate_order_activity,
                self._order,
                **ACTIVITY_CONFIG
            )
            
            if self._cancelled:
                logger.info(f"Order {order_id} cancelled after validation")
                return "Order cancelled"
            
            # Step 3: Manual Review Timer (wait for approval signal)
            logger.info(f"Step 3: Waiting for manual approval for order {order_id}")
            try:
                await workflow.wait_condition(
                    lambda: self._manual_approval_received or self._cancelled,
                    timeout=timedelta(seconds=8)  # Give time for manual approval
                )
                
                if self._cancelled:
                    logger.info(f"Order {order_id} cancelled during manual review")
                    return "Order cancelled"
                    
                if not self._manual_approval_received:
                    logger.warning(f"Manual approval timeout for order {order_id} - proceeding anyway")
                else:
                    logger.info(f"Manual approval received for order {order_id}")
                    
            except TimeoutError:
                logger.warning(f"Manual approval timeout for order {order_id} - proceeding anyway")
            
            # Step 4: Charge Payment
            logger.info(f"Step 4: Charging payment for order {order_id}")
            payment_result = await workflow.execute_activity(
                charge_payment_activity,
                self._order,
                payment_id,
                **ACTIVITY_CONFIG
            )
            
            logger.info(f"Payment charged successfully: {payment_result}")
            
            # Step 5: Start Shipping Workflow (Child)
            logger.info(f"Step 5: Starting shipping workflow for order {order_id}")
            shipping_result = await workflow.execute_child_workflow(
                ShippingWorkflow.run,
                self._order,
                id=f"shipping-{order_id}",
                task_queue="shipping-tq"
            )
            
            logger.info(f"Order {order_id} completed successfully: {shipping_result}")
            return f"Order completed: {shipping_result}"
            
        except Exception as e:
            logger.error(f"Order workflow failed for {order_id}: {e}")
            raise

    @workflow.signal
    def cancel_order(self) -> None:
        """Cancel the order"""
        order_id = self._order.get("order_id") if self._order else "unknown"
        logger.info(f"Cancellation signal received for order {order_id}")
        self._cancelled = True

    @workflow.signal
    def approve_order(self) -> None:
        """Manually approve the order"""
        order_id = self._order.get("order_id") if self._order else "unknown"
        logger.info(f"Manual approval signal received for order {order_id}")
        self._manual_approval_received = True

    @workflow.signal
    def update_address(self, new_address: Dict[str, Any]) -> None:
        """Update shipping address"""
        if self._order:
            self._order["address"] = new_address
            order_id = self._order.get("order_id", "unknown")
            logger.info(f"Address updated for order {order_id}: {new_address}")
            self._address_updated = True

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """Get current order status"""
        return {
            "order": self._order,
            "cancelled": self._cancelled,
            "approved": self._manual_approval_received,
            "address_updated": self._address_updated
        }