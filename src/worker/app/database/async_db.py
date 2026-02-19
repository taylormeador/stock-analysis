import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from contextlib import asynccontextmanager

ASYNC_STOCK_ANALYSIS_DB = os.getenv("ASYNC_STOCK_ANALYSIS_DB", "")

Base = declarative_base()

# Create the async engine
engine = create_async_engine(ASYNC_STOCK_ANALYSIS_DB, echo=False)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# Dependency to get the database session
async def get_db() -> AsyncSession:  # type: ignore
    async with AsyncSessionLocal() as session:
        yield session  # type: ignore


@asynccontextmanager
async def get_connection():
    async with engine.connect() as conn:
        yield conn
