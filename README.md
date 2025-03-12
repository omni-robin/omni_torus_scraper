Torus Reddit Scraper API 🚀

A FastAPI-based Reddit Scraper that provides real-time and on-demand Reddit data via REST API and WebSocket. This API integrates with the Torus Memory Organ to store scraped posts (signed using a Polkadot wallet) by default. You can disable saving on a per-request basis using the do_not_save parameter.

	Note: All sensitive configuration (Reddit credentials, Polkadot wallet seed, Torus Memory URL) is loaded from a .env file.

⸻

Overview

The Torus Reddit Scraper API offers two primary interfaces:
	1.	REST API (/scrape):
Perform one-time scraping of Reddit posts with support for filtering by subreddits, keywords, score, NSFW flag, post type, flair, and optional comment retrieval. By default, scraped posts are also sent to the Torus Memory Organ.
	2.	WebSocket API (/ws/subscribe):
Subscribe to a live stream of Reddit posts that match specified filters. New posts are pushed in real time to connected clients and also stored in the Torus Memory Organ unless the client opts out.

⸻

Features
	•	On-Demand Scraping: Fetch posts using customizable filters.
	•	Real-Time Streaming: Subscribe via WebSocket for live updates.
	•	Torus Memory Organ Integration: Automatically store scraped posts with cryptographic signing using your Polkadot wallet.
	•	Opt-Out Saving: Use the do_not_save flag if you only need transient data.
	•	Configuration via .env: All credentials and endpoints are loaded securely from a .env file.
	•	Easy Deployment: Host with uvicorn and use tools like tmux or ngrok for production readiness.

⸻

Installation & Setup

1️⃣ Clone the Repository

git clone https://github.com/your-username/reddit-scraper-api.git
cd reddit-scraper-api

2️⃣ Set Up a Virtual Environment

python3 -m venv venv
source venv/bin/activate

3️⃣ Install Dependencies

pip install -r requirements.txt

Ensure you have installed packages such as FastAPI, uvicorn, praw, python-dotenv, and requests.

4️⃣ Create a .env File

In the project root, create a file named .env with the following content:

# Reddit API Credentials
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
USER_AGENT=your_custom_user_agent

# Polkadot Wallet Seed (for signing data)
POLKADOT_WALLET_SEED=your_polkadot_wallet_seed

# Torus Memory Organ URL (to save scraped posts)
TORUS_MEMORY_URL=https://your-torus-organ/api/memories/create

	•	Reddit Credentials: Obtain these by creating a Reddit app.
	•	Polkadot Wallet Seed: Used to sign posts for authenticity.
	•	Torus Memory URL: The endpoint for saving posts. If this is not set, posts will not be stored.

5️⃣ Start the FastAPI Server

Run the application using uvicorn:

python reddit_scraper_api.py

This starts the API on 0.0.0.0:8000 with auto-reload enabled (for development).

⸻

API Usage

1️⃣ REST API (Ad Hoc Scraping)

Endpoint:

GET /scrape

(For hosted deployments, prefix with your base URL, e.g., https://api.omni-torus.ngrok.app/scrape.)

Query Parameters:

Parameter	Type	Description
subreddits	List[str]	Subreddits to scrape (e.g., technology,news). Defaults to all if omitted.
keywords	List[str]	Keywords to filter posts (searched in title and body).
min_score	int	Minimum upvote score required.
include_nsfw	bool	Whether to include NSFW posts (default: true).
is_self	bool or null	true for text posts only, false for link posts only, or omitted for both.
flair	List[str]	Allowed post flairs (case-insensitive).
fetch_comments	bool	Whether to retrieve top-level comments (default: false).
comments_limit	int	Number of comments per post if enabled (default: 5).
sort_by	str	Sorting method: hot, new, top, or rising (default: hot).
limit	int	Number of posts to retrieve (default: 10).
do_not_save	bool	If true, do not save the scraped data to Torus (default: false).

Example Request:

curl -u your_username:your_password "https://api.omni-torus.ngrok.app/scrape?subreddits=technology&keywords=AI&limit=3&do_not_save=true"

Example Response:

{
    "posts": [
        {
            "id": "abc123",
            "title": "AI in 2024",
            "selftext": "OpenAI announces a new breakthrough...",
            "url": "https://reddit.com/r/technology/abc123",
            "score": 150,
            "subreddit": "technology",
            "flair": "News",
            "num_comments": 42,
            "comments": [
                "Amazing development!",
                "What about ethical implications?"
            ]
        }
    ]
}

Posts will be saved to the Torus Memory Organ by default unless do_not_save=true is specified.

⸻

2️⃣ WebSocket API (Real-Time Subscription)

Endpoint:

GET /ws/subscribe

(For hosted deployments: wss://api.omni-torus.ngrok.app/ws/subscribe)

How to Connect:

Using wscat:

wscat -c wss://api.omni-torus.ngrok.app/ws/subscribe -H "Authorization: Basic $(echo -n 'your_username:your_password' | base64)"

Subscription Request Format:

Send a JSON message after connecting:

{
    "subreddits": ["technology", "AI"],
    "keywords": ["OpenAI", "GPT-4"],
    "min_score": 10,
    "fetch_comments": true,
    "comments_limit": 5,
    "do_not_save": false
}

	•	do_not_save: Set to true if you wish to disable storing matching posts to Torus.
	•	Other fields are optional and allow you to filter incoming posts.

Example Notification:

Once subscribed, you will receive JSON messages like:

{
    "id": "xyz789",
    "title": "Breakthrough in AI",
    "selftext": "A new AI model surpasses GPT-4...",
    "url": "https://reddit.com/r/technology/xyz789",
    "score": 120,
    "subreddit": "technology",
    "flair": "Discussion",
    "num_comments": 15,
    "comments": [
        "This is amazing!",
        "What about its impact on jobs?"
    ]
}

Each new post that meets your criteria is pushed to your client and saved to Torus unless opted out.

⸻

Deployment & Best Practices

Running the App:

For local development or production testing, you can run:

python reddit_scraper_api.py

This starts uvicorn on port 8000. In production, consider using process managers (e.g., Gunicorn or Docker) and tools like tmux to keep the server running.

Exposing the API:

To expose your local API for external testing, use ngrok:

tmux new -s ngrok
ngrok http 8000 --basic-auth="your_username:your_password"

Copy the generated ngrok URL and update your client requests accordingly.

Security Considerations:
	•	Keep your .env file secure: Do not commit it to version control.
	•	Authentication: For hosted deployments, use Basic Auth (or another secure method) to protect your API endpoints.
	•	Logging: Monitor logs for any errors, especially for external API calls and Torus Memory Organ submissions.

Future Improvements:
	•	Add actual integration with a Polkadot wallet library (instead of simulated signing).
	•	Implement enhanced error handling and automatic retries for external API calls.
	•	Containerize the application using Docker for easier deployment.
	•	Consider adding OAuth2/JWT authentication for increased security.

⸻

License

This project is open-source under the MIT License.

⸻

Contributors
	•	@omni-robin – Creator & Maintainer
