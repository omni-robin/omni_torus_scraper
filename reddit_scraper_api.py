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
    - Comprehensive error handling and.

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
# Reddit API Configuration (Loaded from .env file)
# ----------------------------------------------------------------------
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
USER_AGENT = os.getenv("USER_AGENT")

try:
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=USER_AGENT
    )
except Exception as e:
    logger.exception("Failed to initialize the Reddit instance.")
    raise e

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

    Args:
        submission: A PRAW submission object.

    Returns:
        A dictionary containing post details.
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

# ----------------------------------------------------------------------
# Main Block for Local Testing
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("reddit_scraper_api:app", host="0.0.0.0", port=4444, reload=True)
