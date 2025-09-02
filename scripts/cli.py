import asyncio
import click
import uuid
from temporalio.client import Client

@click.group()
def cli():
    """Temporal Order Management CLI"""
    pass

@cli.command()
@click.argument('order_id')
@click.option('--payment-id', default=None, help='Payment ID (auto-generated if not provided)')
def start_order(order_id, payment_id):
    """Start a new order workflow"""
    asyncio.run(_start_order(order_id, payment_id))

async def _start_order(order_id: str, payment_id: str = None):
    if not payment_id:
        payment_id = str(uuid.uuid4())
    
    client = await Client.connect("localhost:7233")
    handle = await client.start_workflow(
        "OrderWorkflow",
        args=[order_id, payment_id],
        id=f"order-{order_id}",
        task_queue="main-tq"
    )
    
    click.echo(f"Started order workflow: {handle.id}")
    click.echo(f"Payment ID: {payment_id}")

@cli.command()
@click.argument('order_id')
def approve(order_id):
    """Manually approve an order"""
    asyncio.run(_approve_order(order_id))

async def _approve_order(order_id: str):
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle(f"order-{order_id}")
    await handle.signal("approve_order")
    click.echo(f"Sent approval signal to order {order_id}")

@cli.command()
@click.argument('order_id')
def status(order_id):
    """Get order status"""
    asyncio.run(_get_status(order_id))

async def _get_status(order_id: str):
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle(f"order-{order_id}")
    status = await handle.query("get_status")
    click.echo(f"Order {order_id} status:")
    click.echo(f"  Order data: {status.get('order')}")
    click.echo(f"  Cancelled: {status.get('cancelled')}")
    click.echo(f"  Approved: {status.get('approved')}")

if __name__ == '__main__':
    cli()