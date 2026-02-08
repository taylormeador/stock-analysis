from setuptools import setup, find_packages

setup(
    name="stock-analysis-api",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi==0.115.5",
        "uvicorn[standard]==0.32.1",
        "pydantic==2.10.3",
        "pydantic-settings==2.6.1",
        "httpx==0.28.1",
        "sqlalchemy[asyncio]==2.0.46",
        "asyncpg==0.30.0",
        "pandas<3.0.0",
        "yfinance==1.1.0",
        "redis==7.1.0",
    ],
)
