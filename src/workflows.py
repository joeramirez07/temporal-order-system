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
    async def run(self, order: Dict[str, Any], parent_workflow_id: str) -> str:
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
            
            # Signal parent workflow about dispatch failure
            try:
                parent_handle = workflow.get_external_workflow_handle(parent_workflow_id)
                await parent_handle.signal("dispatch_failed", str(e))
                logger.info(f"Signaled parent workflow {parent_workflow_id} about dispatch failure")
            except Exception as signal_error:
                logger.error(f"Failed to signal parent workflow: {signal_error}")
            
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
        self._dispatch_failed_reason: Optional[str] = None
        self._shipping_retry_count = 0

    @workflow.run
    async def run(self, order_id: str, payment_id: str) -> str:
        """Run the complete order workflow"""
        workflow_id = workflow.info().workflow_id
        logger.info(f"Starting order workflow {workflow_id} for {order_id} with payment {payment_id}")
        
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
            
            # Step 5: Start Shipping Workflow (Child) with retry logic
            shipping_result = await self._handle_shipping_with_retry(order_id, workflow_id)
            
            logger.info(f"Order {order_id} completed successfully: {shipping_result}")
            return f"Order completed: {shipping_result}"
            
        except Exception as e:
            logger.error(f"Order workflow failed for {order_id}: {e}")
            raise

    async def _handle_shipping_with_retry(self, order_id: str, workflow_id: str) -> str:
        """Handle shipping with retry logic when dispatch fails"""
        max_shipping_retries = 3
        
        while self._shipping_retry_count < max_shipping_retries:
            try:
                logger.info(f"Step 5: Starting shipping workflow for order {order_id} (attempt {self._shipping_retry_count + 1})")
                
                # Reset dispatch failed flag
                self._dispatch_failed_reason = None
                
                # Start shipping workflow
                shipping_result = await workflow.execute_child_workflow(
                    ShippingWorkflow.run,
                    self._order,
                    workflow_id,
                    id=f"shipping-{order_id}-{self._shipping_retry_count}",
                    task_queue="shipping-tq"
                )
                
                return shipping_result
                
            except Exception as e:
                self._shipping_retry_count += 1
                logger.error(f"Shipping attempt {self._shipping_retry_count} failed for order {order_id}: {e}")
                
                # Wait a bit for potential signal from child workflow
                try:
                    await workflow.wait_condition(
                        lambda: self._dispatch_failed_reason is not None,
                        timeout=timedelta(seconds=2)
                    )
                    if self._dispatch_failed_reason:
                        logger.info(f"Received dispatch failure signal: {self._dispatch_failed_reason}")
                except TimeoutError:
                    pass
                
                if self._shipping_retry_count >= max_shipping_retries:
                    logger.error(f"All shipping attempts failed for order {order_id}")
                    raise Exception(f"Shipping failed after {max_shipping_retries} attempts: {e}")
                
                # Wait before retry
                await workflow.sleep(1)
        
        raise Exception("Shipping retry logic error")

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

    @workflow.signal
    def dispatch_failed(self, reason: str) -> None:
        """Handle dispatch failure signal from child workflow"""
        order_id = self._order.get("order_id") if self._order else "unknown"
        logger.warning(f"Dispatch failed signal received for order {order_id}: {reason}")
        self._dispatch_failed_reason = reason

    @workflow.query
    def get_status(self) -> Dict[str, Any]:
        """Get current order status"""
        return {
            "order": self._order,
            "cancelled": self._cancelled,
            "approved": self._manual_approval_received,
            "address_updated": self._address_updated,
            "shipping_retry_count": self._shipping_retry_count,
            "dispatch_failed_reason": self._dispatch_failed_reason
        }