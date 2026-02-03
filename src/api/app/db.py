import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("STOCK_ANALYSIS_DB", "")

Base = declarative_base()

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create a session maker
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
