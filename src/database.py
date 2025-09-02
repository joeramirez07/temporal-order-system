import asyncio
import asyncpg
import logging
from datetime import datetime
from typing import Optional
import json

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string or "postgresql://postgres:password@localhost:5433/temporal_orders"
        self.pool: Optional[asyncpg.Pool] = None
    
    async def init_pool(self):
        """Initialize connection pool"""
        try:
            self.pool = await asyncpg.create_pool(self.connection_string, max_size=20)
            logger.info("Database connection pool initialized")
            await self.create_tables()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def create_tables(self):
        """Create database tables if they don't exist"""
        async with self.pool.acquire() as conn:
            # Orders table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id VARCHAR(255) PRIMARY KEY,
                    state VARCHAR(50) NOT NULL,
                    items_json TEXT,
                    address_json TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Payments table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id VARCHAR(255) PRIMARY KEY,
                    order_id VARCHAR(255) REFERENCES orders(id),
                    status VARCHAR(50) NOT NULL,
                    amount INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Events table for logging
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    order_id VARCHAR(255) REFERENCES orders(id),
                    type VARCHAR(100) NOT NULL,
                    payload_json TEXT,
                    ts TIMESTAMP DEFAULT NOW()
                )
            """)
            
            logger.info("Database tables created/verified")
    
    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

# Global database instance
db = Database()

async def get_db_pool():
    """Get the database pool"""
    if not db.pool:
        await db.init_pool()
    return db.pool