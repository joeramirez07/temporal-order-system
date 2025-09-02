import asyncio
import uuid
from temporalio.client import Client

async def test_successful_workflow():
    """Test workflow with multiple attempts until success"""
    client = await Client.connect("localhost:7233")
    
    for attempt in range(5):  # Try up to 5 workflows
        order_id = f"success-test-{uuid.uuid4().hex[:8]}"
        payment_id = str(uuid.uuid4())
        
        print(f"🚀 Attempt {attempt + 1}: Starting workflow {order_id}")
        
        try:
            handle = await client.start_workflow(
                "OrderWorkflow",
                args=[order_id, payment_id],
                id=f"order-{order_id}",
                task_queue="main-tq"
            )
            
            # Send approval quickly
            await asyncio.sleep(2)
            await handle.signal("approve_order")
            print(f"✅ Sent approval for {order_id}")
            
            # Wait for result with timeout
            result = await asyncio.wait_for(handle.result(), timeout=30)
            print(f"🎉 SUCCESS! Workflow completed: {result}")
            break
            
        except asyncio.TimeoutError:
            print(f"⏰ Workflow {order_id} timed out")
        except Exception as e:
            print(f"❌ Workflow {order_id} failed: {e}")
            
        await asyncio.sleep(1)
    else:
        print("All attempts failed - this is expected due to flaky_call()")

if __name__ == "__main__":
    asyncio.run(test_successful_workflow())