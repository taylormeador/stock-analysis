from setuptools import setup, find_packages

setup(
    name="stock-analysis-worker",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "boto3==1.42.39",
        "celery==5.6.2",
        "dotenv==0.9.9",
        "redis==7.1.0",
        "psycopg2-binary==2.9.11",
        "sqlalchemy==2.0.46",
        "flower==2.0.1",
        "torch==2.10.0",
        "transformers==5.0.0",
        "yfinance==1.1.0",
        "pandas<3",
        "pandas-ta==0.4.71b0",
        "scikit-learn==1.8.0",
        "xgboost==2.1.3",
        "lightgbm==4.6.0",
        "mlflow==3.9.0",
        "matplotlib==3.10.0",
        "seaborn==0.13.2",
        "pyarrow==22.0.0",
    ],
)
