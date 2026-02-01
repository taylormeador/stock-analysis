from fastapi import APIRouter
import logging
import logic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/whats-hot")
def get_whats_hot():
    logger.info("calculating data for hot dashboard")

    ticker_mentions = logic.get_ticker_mentions()
    top_comments = logic.get_top_comments()

    logger.info("got whats hot data")

    dfs = {
        "ticker_mentions": ticker_mentions.to_dict("records"),
        "top_comments": top_comments.to_dict("records"),
    }

    return {"data": dfs}
