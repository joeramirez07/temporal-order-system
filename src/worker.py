import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker

from .workflows import OrderWorkflow, ShippingWorkflow
from .activities import (
    receive_order_activity,
    validate_order_activity,
    charge_payment_activity,
    prepare_package_activity,
    dispatch_carrier_activity
)
from .database import db

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to run workers"""
    
    # Initialize database
    logger.info("Initializing database...")
    await db.init_pool()
    
    # Connect to Temporal
    logger.info("Connecting to Temporal server...")
    client = await Client.connect("localhost:7233")
    
    # Create workers
    main_worker = Worker(
        client,
        task_queue="main-tq",
        workflows=[OrderWorkflow],
        activities=[
            receive_order_activity,
            validate_order_activity,
            charge_payment_activity
        ]
    )
    
    shipping_worker = Worker(
        client,
        task_queue="shipping-tq",
        workflows=[ShippingWorkflow],
        activities=[
            prepare_package_activity,
            dispatch_carrier_activity
        ]
    )
    
    # Start workers
    logger.info("Starting workers...")
    logger.info("Workers ready! Press Ctrl+C to stop.")
    
    try:
        await asyncio.gather(
            main_worker.run(),
            shipping_worker.run()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down workers...")
    finally:
        await db.close()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())