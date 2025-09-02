import asyncio
import asyncpg

async def check_database():
    """Check what's actually in our database"""
    try:
        conn = await asyncpg.connect("postgresql://postgres:password@localhost:5433/temporal_orders")
        
        print("=== DATABASE STATUS ===")
        
        # Check orders
        orders = await conn.fetch("SELECT * FROM orders ORDER BY created_at DESC LIMIT 5")
        print(f"\nOrders ({len(orders)} recent):")
        for order in orders:
            print(f"  {order['id']}: {order['state']} (created: {order['created_at']})")
        
        # Check payments  
        payments = await conn.fetch("SELECT * FROM payments ORDER BY created_at DESC LIMIT 5")
        print(f"\nPayments ({len(payments)} recent):")
        for payment in payments:
            print(f"  {payment['payment_id']}: {payment['status']} (amount: {payment['amount']})")
        
        # Check events
        events = await conn.fetch("SELECT * FROM events ORDER BY ts DESC LIMIT 10")
        print(f"\nEvents ({len(events)} recent):")
        for event in events:
            print(f"  {event['order_id']}: {event['type']} at {event['ts']}")
            
        await conn.close()
        
    except Exception as e:
        print(f"Database check failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_database())