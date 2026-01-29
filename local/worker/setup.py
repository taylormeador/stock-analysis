from setuptools import setup, find_packages

setup(
    name="stock-analysis-worker",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "celery==5.6.2",
        "dotenv==0.9.9",
        "redis==7.1.0",
        "psycopg2-binary==2.9.11",
        "sqlalchemy==2.0.46",
        "flower==2.0.1",
        "torch==2.10.0",
        "transformers==5.0.0",
        "yfinance==1.1.0",
    ],
)
