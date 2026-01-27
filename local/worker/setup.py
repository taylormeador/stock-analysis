from setuptools import setup, find_packages

setup(
    name="stock-analysis-worker",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "celery==5.3.4",
        "redis==5.0.1",
        "psycopg2-binary==2.9.9",
        "sqlalchemy==2.0.23",
        "praw==7.7.1",
        "flower==2.0.1",
        "torch==2.10.0",
        "transformers==5.0.0",
        "python-dotenv",
    ],
)
