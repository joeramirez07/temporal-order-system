from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from temporalio.client import Client
from temporalio.exceptions import WorkflowNotFoundError
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional

app = FastAPI(title="Temporal Order API", version="1.0.0")
logger = logging.getLogger(__name__)

# Global client - will be initialized on startup
temporal_client = None

# Pydantic models for request/response
class StartOrderRequest(BaseModel):
    payment_id: Optional[str] = None

class UpdateAddressRequest(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str

class OrderStatusResponse(BaseModel):
    order_id: str
    workflow_id: str
    status: Dict[str, Any]
    is_running: bool

@app.on_event("startup")
async def startup_event():
    """Initialize Temporal client on startup"""
    global temporal_client
    try:
        temporal_client = await Client.connect("localhost:7233")
        logger.info("Connected to Temporal server")
    except Exception as e:
        logger.error(f"Failed to connect to Temporal: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    global temporal_client
    if temporal_client:
        await temporal_client.close()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Temporal Order API is running", "status": "healthy"}

@app.post("/orders/{order_id}/start", response_model=Dict[str, str])
async def start_order(order_id: str, request: StartOrderRequest):
    """Start an OrderWorkflow"""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal client not initialized")
    
    payment_id = request.payment_id or str(uuid.uuid4())
    workflow_id = f"order-{order_id}"
    
    try:
        # Check if workflow is already running
        try:
            existing_handle = temporal_client.get_workflow_handle(workflow_id)
            status = await existing_handle.describe()
            if status.status.name in ['RUNNING', 'CONTINUED_AS_NEW']:
                raise HTTPException(
                    status_code=409, 
                    detail=f"Order workflow {order_id} is already running"
                )
        except WorkflowNotFoundError:
            pass  # Workflow doesn't exist, which is what we want
        
        # Start new workflow
        handle = await temporal_client.start_workflow(
            "OrderWorkflow",
            args=[order_id, payment_id],
            id=workflow_id,
            task_queue="main-tq"
        )
        
        logger.info(f"Started order workflow for {order_id} with payment {payment_id}")
        
        return {
            "message": f"Order workflow started for {order_id}",
            "workflow_id": handle.id,
            "order_id": order_id,
            "payment_id": payment_id
        }
    except Exception as e:
        logger.error(f"Failed to start workflow for {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orders/{order_id}/signals/cancel")
async def cancel_order(order_id: str):
    """Send cancel signal to order"""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal client not initialized")
    
    try:
        handle = temporal_client.get_workflow_handle(f"order-{order_id}")
        await handle.signal("cancel_order")
        
        logger.info(f"Cancel signal sent to order {order_id}")
        return {"message": f"Cancel signal sent to order {order_id}"}
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Order {order_id} workflow not found")
    except Exception as e:
        logger.error(f"Failed to cancel order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orders/{order_id}/signals/approve")
async def approve_order(order_id: str):
    """Send approval signal to order"""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal client not initialized")
    
    try:
        handle = temporal_client.get_workflow_handle(f"order-{order_id}")
        await handle.signal("approve_order")
        
        logger.info(f"Approval signal sent to order {order_id}")
        return {"message": f"Approval signal sent to order {order_id}"}
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Order {order_id} workflow not found")
    except Exception as e:
        logger.error(f"Failed to approve order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orders/{order_id}/signals/update-address")
async def update_address(order_id: str, request: UpdateAddressRequest):
    """Update shipping address"""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal client not initialized")
    
    address = {
        "street": request.street,
        "city": request.city,
        "state": request.state,
        "zip_code": request.zip_code
    }
    
    try:
        handle = temporal_client.get_workflow_handle(f"order-{order_id}")
        await handle.signal("update_address", address)
        
        logger.info(f"Address updated for order {order_id}")
        return {
            "message": f"Address updated for order {order_id}",
            "new_address": address
        }
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Order {order_id} workflow not found")
    except Exception as e:
        logger.error(f"Failed to update address for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders/{order_id}/status", response_model=OrderStatusResponse)
async def get_order_status(order_id: str):
    """Get current order status"""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal client not initialized")
    
    workflow_id = f"order-{order_id}"
    
    try:
        handle = temporal_client.get_workflow_handle(workflow_id)
        
        # Get workflow description to check if it's running
        description = await handle.describe()
        is_running = description.status.name in ['RUNNING', 'CONTINUED_AS_NEW']
        
        # Get current status via query
        if is_running:
            status = await handle.query("get_status")
        else:
            # For completed/failed workflows, we can still get some info
            status = {
                "workflow_status": description.status.name,
                "start_time": description.start_time,
                "close_time": description.close_time,
                "execution_time": description.execution_time
            }
        
        return OrderStatusResponse(
            order_id=order_id,
            workflow_id=workflow_id,
            status=status,
            is_running=is_running
        )
        
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Order {order_id} workflow not found")
    except Exception as e:
        logger.error(f"Failed to get status for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders/{order_id}/result")
async def get_order_result(order_id: str):
    """Get final result of completed workflow"""
    if not temporal_client:
        raise HTTPException(status_code=503, detail="Temporal client not initialized")
    
    try:
        handle = temporal_client.get_workflow_handle(f"order-{order_id}")
        
        # Check if workflow is completed
        description = await handle.describe()
        if description.status.name == 'RUNNING':
            raise HTTPException(
                status_code=409, 
                detail=f"Order {order_id} is still running"
            )
        
        # Get the result
        try:
            result = await handle.result()
            return {
                "order_id": order_id,
                "status": "completed",
                "result": result
            }
        except Exception as workflow_error:
            return {
                "order_id": order_id,
                "status": "failed",
                "error": str(workflow_error)
            }
            
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Order {order_id} workflow not found")
    except Exception as e:
        logger.error(f"Failed to get result for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)