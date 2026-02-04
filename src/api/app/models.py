from sqlalchemy import (
    Table,
    Text,
    Column,
    Date,
    Integer,
    Float,
    String,
    MetaData,
    TIMESTAMP,
    BigInteger,
    Numeric,
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
