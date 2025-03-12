#!/usr/bin/env python3
"""
OmniLabs Reddit Scraper API for Torus Memory Organ

This module implements a FastAPI application that provides both a one-time REST
scraping endpoint and a dynamic WebSocket subscription endpoint. It uses the PRAW
library to interface with Reddit and supports extensive filtering options.

Developed with enterprise standards in mind:
    - Data validation using Pydantic models.
    - Structured logging with the standard logging module.
    - Thread-safe handling of global state using locks.
    - Comprehensive error handling.

Configuration (Reddit credentials, Polkadot wallet seed, Torus Memory URL) are read from a .env file.
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
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
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
# Configuration from Environment Variables
# ----------------------------------------------------------------------
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
USER_AGENT = os.getenv("USER_AGENT", "torus_info")
POLKADOT_WALLET_SEED = os.getenv("POLKADOT_WALLET_SEED")  # Used by the polkadot_wallet module
TORUS_MEMORY_URL = os.getenv("TORUS_MEMORY_URL")  # e.g., https://your-torus-organ/api/memories/create

# ----------------------------------------------------------------------
# Reddit API Instance (initialized later)
# ----------------------------------------------------------------------
reddit = None

# ----------------------------------------------------------------------
# FastAPI Application Setup
# ----------------------------------------------------------------------
app = FastAPI(title="Enterprise-Ready Reddit Scraper API")

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
        description="Minimum score (upvotes) required for a post."
    )
    include_nsfw: bool = Field(
        default=True,
        description="Whether to include NSFW posts."
    )
    is_self: Optional[bool] = Field(
        default=None,
        description="If True, only self (text) posts; if False, only link posts; if None, both."
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
    Extract relevant fields from a Reddit submission into a dictionary.
    """
    return {
        "id": submission.id,
        "title": submission.title,
        "selftext": submission.selftext or "",
        "url": submission.url,
        "score": submission.score,
        "subreddit": str(submission.subreddit.display_name),
        "flair": (submission.link_flair_text or "") if hasattr(submission, "link_flair_text") else "",
        "num_comments": submission.num_comments
    }

def get_comments(submission: praw.models.Submission, limit: int) -> List[str]:
    """
    Retrieve top-level comments from a submission up to the specified limit.
    """
    comments = []
    try:
        submission.comments.replace_more(limit=0)
    except Exception as e:
        logger.error(f"Error expanding comments for submission {submission.id}: {e}")
    for i, comment in enumerate(submission.comments):
        if i >= limit:
            break
        try:
            comments.append(comment.body)
        except Exception as e:
            logger.error(f"Error reading comment in submission {submission.id}: {e}")
    return comments

def matches_filters(submission: praw.models.Submission, filters: FilterParams) -> bool:
    """
    Check if a Reddit submission meets the criteria specified in filters.
    """
    if filters.subreddits:
        allowed_subs = {sub.lower() for sub in filters.subreddits}
        if str(submission.subreddit.display_name).lower() not in allowed_subs:
            return False
    if filters.keywords:
        content = (submission.title or "") + " " + (submission.selftext or "")
        content = content.lower()
        if not any(kw.lower() in content for kw in filters.keywords):
            return False
    if filters.min_score is not None:
        if submission.score < filters.min_score:
            return False
    if not filters.include_nsfw:
        if hasattr(submission, "over_18") and submission.over_18:
            return False
    if filters.is_self is not None:
        if filters.is_self and not submission.is_self:
            return False
        if not filters.is_self and submission.is_self:
            return False
    if filters.flair:
        allowed_flairs = {f.lower() for f in filters.flair}
        flair_text = (submission.link_flair_text or "").lower() if hasattr(submission, "link_flair_text") and submission.link_flair_text else ""
        if flair_text not in allowed_flairs:
            return False
    return True

def create_memory(text: str) -> None:
    """
    Submit scraped data (text) to the Torus Memory Organ. Uses the Polkadot wallet
    to sign the message. Any failures are logged.
    
    Note: This function assumes that a separate module (e.g., polkadot_wallet) is available
    that provides signing functionality. For demonstration, we'll simulate signing.
    """
    try:
        # Simulated signing logic. Replace with actual wallet integration.
        creator_address = "polkadot_address_derived_from_seed"
        signature = "signature_of_text"
        
        payload = {
            "creator_address": creator_address,
            "text": text,
            "signature": signature
        }
        resp = requests.post(TORUS_MEMORY_URL, json=payload, timeout=5)
        if resp.status_code != 200:
            logger.error(f"Torus Memory Organ responded with status {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Exception in create_memory: {e}")

# ----------------------------------------------------------------------
# Background Reddit Streaming Worker
# ----------------------------------------------------------------------
def reddit_stream_worker(loop: asyncio.AbstractEventLoop) -> None:
    """
    Continuously streams new Reddit submissions and dispatches matching posts
    to subscribed WebSocket clients based on their filter criteria. Also submits data to Torus if enabled.
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

            store_needed = False
            any_fetch = False
            max_comments = 0

            for subscriber in current_subscribers:
                ws = subscriber["ws"]
                filters: FilterParams = subscriber["filters"]
                if matches_filters(submission, filters):
                    data = prepare_post_data(submission)
                    if filters.fetch_comments:
                        data["comments"] = get_comments(submission, filters.comments_limit)
                    asyncio.run_coroutine_threadsafe(ws.send_json(data), loop)
                    if not subscriber.get("do_not_save", False):
                        store_needed = True
                        if filters.fetch_comments:
                            any_fetch = True
                            if filters.comments_limit > max_comments:
                                max_comments = filters.comments_limit
            if store_needed and TORUS_MEMORY_URL:
                mem_data = prepare_post_data(submission)
                if any_fetch:
                    mem_data["comments"] = get_comments(submission, max_comments)
                try:
                    resp = requests.post(TORUS_MEMORY_URL, json={"posts": [mem_data]}, timeout=5)
                    if resp.status_code != 200:
                        logger.error(f"Torus Memory Organ responded with status {resp.status_code}: {resp.text}")
                except Exception as e:
                    logger.error(f"Failed to send data to Torus Memory Organ for post {submission.id}: {e}")

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

    if TORUS_MEMORY_URL:
        logger.info(f"Torus Memory Organ integration enabled (endpoint: {TORUS_MEMORY_URL}).")
    else:
        logger.warning("TORUS_MEMORY_URL is not set. Scraped data will not be stored in Torus Memory Organ.")

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
    ),
    do_not_save: bool = Query(
        False, description="If true, return the scraped data without saving it to Torus."
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
    try:
        subreddit_obj = reddit.subreddit(subreddit_str)
    except Exception as e:
        logger.error(f"Error accessing subreddit {subreddit_str}: {e}")
        raise HTTPException(status_code=500, detail="Failed to access subreddit(s).")
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

    if not do_not_save and TORUS_MEMORY_URL:
        try:
            resp = requests.post(TORUS_MEMORY_URL, json={"posts": results}, timeout=5)
            if resp.status_code != 200:
                logger.error(f"Torus Memory Organ responded with status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Failed to send scraped data to Torus Memory Organ: {e}")

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
        do_not_save = False
        if "do_not_save" in filters_data:
            do_not_save = bool(filters_data.pop("do_not_save"))
        filters = FilterParams(**filters_data)
    except Exception as e:
        error_msg = "Invalid JSON payload for filter parameters."
        logger.error(f"{error_msg} Error: {e}")
        await websocket.send_json({"error": error_msg})
        await websocket.close()
        return

    subscriber = {"ws": websocket, "filters": filters, "do_not_save": do_not_save}
    with subscribers_lock:
        subscribers.append(subscriber)
    logger.info("New subscriber added with filters: %s (do_not_save=%s)", filters.dict(), do_not_save)

    try:
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        with subscribers_lock:
            if subscriber in subscribers:
                subscribers.remove(subscriber)
        logger.info("Subscriber disconnected.")

# ----------------------------------------------------------------------
# Uvicorn Hosting (run the app)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("reddit_scraper_api:app", host="0.0.0.0", port=8000, reload=True)
