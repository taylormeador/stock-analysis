from fastapi import APIRouter
import logging
import logic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/whats-hot")
async def get_whats_hot():
    logger.info("calculating data for hot dashboard")

    top_comments = await logic.get_top_comments()
    ticker_mentions = await logic.get_ticker_mentions()

    logger.info("got whats hot data")

    dfs = {
        "ticker_mentions": ticker_mentions.to_dict("records"),
        "top_comments": top_comments.to_dict("records"),
    }

    return {"data": dfs}


if __name__ == "__main__":
    import asyncio

    asyncio.run(get_whats_hot())
