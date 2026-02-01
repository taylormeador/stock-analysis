from fastapi import FastAPI
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/")
def index():
    return {"hello": "world"}


@app.get("/health")
def health():
    return {"status": "up"}
