import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger("student-dropout-system.db")


class MongoDBManager:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


db_manager = MongoDBManager()


async def connect_to_mongo(
    uri: str,
    database_name: str,
    max_retries: int = 5,
    initial_delay: float = 1.0,
) -> AsyncIOMotorClient:
    """
    Connects to MongoDB with retry and exponential backoff.
    Fails loudly with RuntimeError if connection cannot be established.
    """
    delay = initial_delay
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Attempting MongoDB connection (attempt %d/%d)...", attempt, max_retries)
            client: AsyncIOMotorClient = AsyncIOMotorClient(
                uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            # Ping the admin database to verify active connection
            await client.admin.command("ping")
            db_manager.client = client
            db_manager.db = client[database_name]
            logger.info("MongoDB connected successfully to database '%s'", database_name)
            return client
        except Exception as e:
            last_error = e
            logger.warning(
                "MongoDB connection failed on attempt %d/%d: %s. Retrying in %.1fs...",
                attempt,
                max_retries,
                str(e),
                delay,
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2.0  # Exponential backoff

    error_msg = (
        f"CRITICAL: Failed to connect to MongoDB after {max_retries} attempts. "
        f"Last error: {last_error}"
    )
    logger.critical(error_msg)
    raise RuntimeError(error_msg)


async def close_mongo_connection() -> None:
    """Closes the active MongoDB connection."""
    if db_manager.client is not None:
        logger.info("Closing MongoDB connection...")
        db_manager.client.close()
        db_manager.client = None
        db_manager.db = None
        logger.info("MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:
    """Returns the active MongoDB database instance."""
    if db_manager.db is None:
        raise RuntimeError("Database connection has not been initialized.")
    return db_manager.db


async def ping_database() -> bool:
    """Checks if the MongoDB database is reachable."""
    if db_manager.client is None:
        return False
    try:
        await db_manager.client.admin.command("ping")
        return True
    except Exception as e:
        logger.error("MongoDB ping failed: %s", str(e))
        return False
