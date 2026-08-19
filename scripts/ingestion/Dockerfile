FROM python:3.13-slim

WORKDIR /app

# polars' standard wheel needs AVX2/FMA/BMI1; the -lts-cpu build works on any CPU.
# thetadata imports dotenv unconditionally but doesn't declare it as a dependency.
RUN pip install --no-cache-dir thetadata pandas pyarrow python-dotenv \
    && pip uninstall -y polars \
    && pip install --no-cache-dir "polars-lts-cpu>=1.33.1"

COPY theta_5min_candles.py .

ENTRYPOINT ["python", "-u", "theta_5min_candles.py"]
