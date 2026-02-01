from fastapi import FastAPI
import logging
import routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(routes.router)


@app.get("/")
async def index():
    return {"hello": "world"}


@app.get("/health")
async def health():
    return {"status": "up"}
