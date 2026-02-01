import os
import logging

from sqlalchemy import create_engine
from contextlib import contextmanager


DATABASE_URL = os.environ["STOCK_ANALYSIS_DB"]


logger = logging.getLogger(__name__)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)


@contextmanager
def get_connection():
    """Get a connection from the pool for this task"""
    conn = engine.connect()
    try:
        yield conn
    except Exception as e:
        logger.error(f"error in db conn: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()  # Returns connection to pool, doesn't actually close it
