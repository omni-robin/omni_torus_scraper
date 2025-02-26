#!/usr/bin/env python3
"""
Enterprise-Ready Reddit Scraper API

This module implements a FastAPI application that provides both a one-time REST
scraping endpoint and a dynamic WebSocket subscription endpoint. It uses the PRAW
library to interface with Reddit and supports extensive filtering options.

Developed with enterprise standards in mind:
    - Data validation using Pydantic models.
    - Structured logging with the standard logging module.
    - Thread-safe handling of global state using locks.
    - Comprehensive error handling.

Replace the Reddit API credentials with your own credentials before deployment.
"""

import asyncio
import threading
import logging
import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import praw
from dotenv import load_dotenv

# ----------------------------------------------------------------------
# Load Environment Variables
# ----------------------------------------------------------------------
load_dotenv()

# ----------------------------------------------------------------------
# Logging Configuration
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Reddit API Configuration (Replace with your credentials)
# ----------------------------------------------------------------------
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
USER_AGENT = os.getenv("USER_AGENT")

# Do not initialize reddit here.
reddit = None

# ----------------------------------------------------------------------
# FastAPI Application Setup
# ----------------------------------------------------------------------
app = FastAPI(title="Enterprise-Ready Reddit Scraper API")

# For production, update allowed origins appropriately.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------
# Global Subscribers List and Lock
# ----------------------------------------------------------------------
# Subscribers are stored as dictionaries containing the WebSocket connection
# and a FilterParams instance for filtering criteria.
subscribers: List[Dict[str, Any]] = []
subscribers_lock = threading.Lock()

# ----------------------------------------------------------------------
# Pydantic Models for Data Validation
# ----------------------------------------------------------------------
class FilterParams(BaseModel):
    """
    Data model representing filtering criteria for Reddit posts.
    """
    subreddits: Optional[List[str]] = Field(
        default=None,
        description="List of subreddit names to filter by."
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Keywords to search for in the title and selftext."
    )
    min_score: Optional[int] = Field(
        default=None,
        description="Minimum score required for a post."
    )
    include_nsfw: bool = Field(
        default=True,
        description="Whether to include NSFW posts."
    )
    is_self: Optional[bool] = Field(
        default=None,
        description="If True, filter to self posts; if False, filter to link posts."
    )
    flair: Optional[List[str]] = Field(
        default=None,
        description="List of allowed flairs (case-insensitive)."
    )
    fetch_comments: bool = Field(
        default=False,
        description="Whether to retrieve top-level comments."
    )
    comments_limit: int = Field(
        default=5,
        description="Number of top-level comments to fetch per post."
    )

# ----------------------------------------------------------------------
# Utility Functions
# ----------------------------------------------------------------------
def prepare_post_data(submission: praw.models.Submission) -> Dict[str, Any]:
    """
    Extracts and returns essential data from a Reddit submission.
    """
    return {
        "id": submission.id,
        "title": submission.title,
        "selftext": submission.selftext,
        "url": submission.url,
        "score": submission.score,
        "subreddit": submission.subreddit.display_name,
        "author": str(submission.author) if submission.author else None,
        "created_utc": submission.created_utc,
        "over_18": submission.over_18,
        "is_self": submission.is_self,
        "flair": submission.link_flair_text,
        "num_comments": submission.num_comments,
    }


def get_comments(submission: praw.models.Submission, limit: int = 5) -> List[str]:
    """
    Retrieves up to a specified number of top-level comments for a submission.
    """
    try:
        submission.comments.replace_more(limit=0)
        comments = [comment.body for comment in submission.comments.list()[:limit]]
    except Exception as e:
        logger.error(f"Error fetching comments for submission {submission.id}: {e}")
        comments = []
    return comments


def matches_filters(submission: praw.models.Submission, filters: FilterParams) -> bool:
    """
    Determines whether a submission meets the specified filtering criteria.
    """
    # Check subreddit filter.
    if filters.subreddits:
        allowed_subs = {s.lower() for s in filters.subreddits}
        if submission.subreddit.display_name.lower() not in allowed_subs:
            return False

    # Check keywords in the title and selftext.
    if filters.keywords:
        combined_text = f"{submission.title} {submission.selftext}"
        if not any(keyword.lower() in combined_text.lower() for keyword in filters.keywords):
            return False

    # Check minimum score.
    if filters.min_score is not None and submission.score < filters.min_score:
        return False

    # Exclude NSFW posts if not allowed.
    if not filters.include_nsfw and submission.over_18:
        return False

    # Filter by post type.
    if filters.is_self is not None and submission.is_self != filters.is_self:
        return False

    # Filter by flair.
    if filters.flair:
        allowed_flairs = {f.lower() for f in filters.flair}
        flair_text = submission.link_flair_text.lower() if submission.link_flair_text else ""
        if flair_text not in allowed_flairs:
            return False

    return True

# ----------------------------------------------------------------------
# Background Reddit Streaming Worker
# ----------------------------------------------------------------------
def reddit_stream_worker(loop: asyncio.AbstractEventLoop) -> None:
    """
    Continuously streams new Reddit submissions and dispatches matching posts
    to subscribed WebSocket clients based on their filter criteria.
    """
    logger.info("Starting Reddit stream worker.")
    try:
        global reddit
        if reddit is None:
            logger.error("Reddit instance is not initialized. Exiting thread.")
            return

        for submission in reddit.subreddit("all").stream.submissions(skip_existing=True):
            with subscribers_lock:
                current_subscribers = subscribers.copy()

            for subscriber in current_subscribers:
                ws = subscriber["ws"]
                filters: FilterParams = subscriber["filters"]
                if matches_filters(submission, filters):
                    data = prepare_post_data(submission)
                    if filters.fetch_comments:
                        data["comments"] = get_comments(submission, filters.comments_limit)
                    asyncio.run_coroutine_threadsafe(ws.send_json(data), loop)
    except Exception as e:
        logger.exception(f"Exception in reddit_stream_worker: {e}")

# ----------------------------------------------------------------------
# FastAPI Event Handlers
# ----------------------------------------------------------------------
@app.on_event("startup")
async def startup_event() -> None:
    """
    Handles application startup by initializing the Reddit instance and launching
    the Reddit streaming worker in a separate daemon thread.
    """
    global reddit
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=USER_AGENT
        )
        logger.info("Reddit instance created successfully.")
    except Exception as e:
        logger.exception("Failed to initialize the Reddit instance.")
        raise e

    loop = asyncio.get_event_loop()
    thread = threading.Thread(target=reddit_stream_worker, args=(loop,), daemon=True)
    thread.start()
    logger.info("Reddit stream worker thread started.")

# ----------------------------------------------------------------------
# REST API Endpoint: /scrape
# ----------------------------------------------------------------------
@app.get("/scrape", summary="Perform a one-time scrape of Reddit posts based on filters.")
async def scrape(
    subreddits: Optional[List[str]] = Query(
        None, description="List of subreddits to scrape (e.g., technology,news). Defaults to all if omitted."
    ),
    keywords: Optional[List[str]] = Query(
        None, description="Keywords to filter posts (searched in title and selftext)."
    ),
    min_score: Optional[int] = Query(
        None, description="Minimum score (upvotes) required."
    ),
    include_nsfw: bool = Query(
        True, description="Include NSFW posts."
    ),
    is_self: Optional[bool] = Query(
        None, description="Filter by post type: True for self posts, False for link posts."
    ),
    flair: Optional[List[str]] = Query(
        None, description="Allowed flairs (case-insensitive)."
    ),
    fetch_comments: bool = Query(
        False, description="Whether to fetch top-level comments."
    ),
    comments_limit: int = Query(
        5, description="Number of top-level comments to fetch per post."
    ),
    sort_by: str = Query(
        "hot", description="Sorting method: hot, new, top, or rising."
    ),
    limit: int = Query(
        10, description="Number of posts to retrieve."
    )
) -> Dict[str, Any]:
    """
    Executes a one-time Reddit scrape based on dynamic filter parameters.
    """
    filters = FilterParams(
        subreddits=subreddits,
        keywords=keywords,
        min_score=min_score,
        include_nsfw=include_nsfw,
        is_self=is_self,
        flair=flair,
        fetch_comments=fetch_comments,
        comments_limit=comments_limit,
    )

    subreddit_str = "+".join(subreddits) if subreddits else "all"
    subreddit_obj = reddit.subreddit(subreddit_str)

    sort_methods = {
        "hot": subreddit_obj.hot,
        "new": subreddit_obj.new,
        "top": subreddit_obj.top,
        "rising": subreddit_obj.rising,
    }
    sort_func = sort_methods.get(sort_by.lower())
    if not sort_func:
        raise HTTPException(
            status_code=400,
            detail="Invalid sort_by parameter. Use 'hot', 'new', 'top', or 'rising'."
        )

    # Fetch extra posts to account for filtering.
    posts_generator = sort_func(limit=limit * 2)
    results = []
    for post in posts_generator:
        if matches_filters(post, filters):
            data = prepare_post_data(post)
            if fetch_comments:
                data["comments"] = get_comments(post, comments_limit)
            results.append(data)
            if len(results) >= limit:
                break

    return {"posts": results}

# ----------------------------------------------------------------------
# WebSocket Endpoint: /ws/subscribe
# ----------------------------------------------------------------------
@app.websocket("/ws/subscribe")
async def websocket_subscribe(websocket: WebSocket) -> None:
    """
    Accepts WebSocket connections for real-time subscription to Reddit posts.
    """
    await websocket.accept()
    try:
        filters_data = await websocket.receive_json()
        filters = FilterParams(**filters_data)
    except Exception as e:
        error_msg = "Invalid JSON payload for filter parameters."
        logger.error(f"{error_msg} Error: {e}")
        await websocket.send_json({"error": error_msg})
        await websocket.close()
        return

    subscriber = {"ws": websocket, "filters": filters}
    with subscribers_lock:
        subscribers.append(subscriber)
    logger.info("New subscriber added with filters: %s", filters.dict())

    try:
        while True:
            # Maintain the connection with periodic sleep.
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        with subscribers_lock:
            if subscriber in subscribers:
                subscribers.remove(subscriber)
        logger.info("Subscriber disconnected.")

# ----------------------------------------------------------------------
# Main Block for Local Testing
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
