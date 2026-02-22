from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    MetaData,
    Boolean,
)

metadata = MetaData()

tickers = Table(
    "tickers",
    metadata,
    Column("id", Integer, primary_key=True, nullable=False),
    Column("ticker", String(10)),
    Column("is_tracked", Boolean),
)
