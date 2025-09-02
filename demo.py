import asyncio
import uuid
from temporalio.client import Client

async def run_complete_demo():
    """Demonstrate the complete order workflow"""
    client = await Client.connect("localhost:7233")
    
    order_id = f"demo-order-{uuid.uuid4().hex[:8]}"
    payment_id = str(uuid.uuid4())
    
    print(f"🚀 Starting order workflow: {order_id}")
    
    # Start workflow
    handle = await client.start_workflow(
        "OrderWorkflow",
        args=[order_id, payment_id],
        id=f"order-{order_id}",
        task_queue="main-tq"
    )
    
    print(f"📦 Order started with payment ID: {payment_id}")
    
    # Wait a bit, then approve
    await asyncio.sleep(5)
    print("✅ Sending approval signal...")
    await handle.signal("approve_order")
    
    # Check status periodically
    for i in range(10):
        await asyncio.sleep(2)
        try:
            result = await handle.result()
            print(f"🎉 Workflow completed: {result}")
            break
        except:
            # Still running
            status = await handle.query("get_status")
            print(f"⏳ Status check {i+1}: Order state = {status.get('order', {}).get('state', 'unknown')}")
    
    print("✨ Demo complete!")

if __name__ == "__main__":
    asyncio.run(run_complete_demo())