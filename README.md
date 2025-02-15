# **Usage Guide for Torus Reddit Scraper API**

Please keep in mind that this is being developed actively, and will change.
This version only handles the scrape and subscribe part.
Code to add the scraped information to the Torus knowledge organ will soon be added.

Current rate limits are set to 100 posts / minute on the hosted version.
Please contact OmniLabs in any of the official Torus channels to get an auth token to use the OmniLabs hosted API.

## **Overview**
This guide explains how to use the **Reddit Scraper API**, which provides **real-time and on-demand Reddit data** via **REST API and WebSocket**. The API is accessible at **https://api.omni-torus.ngrok.app** and allows both **ad hoc scraping** and **live subscription** to Reddit posts based on filters.

---

## **1️⃣ REST API (Ad Hoc Scraping)**

The `/scrape` endpoint allows users to request Reddit posts on demand based on various filters.

### **🔹 Endpoint:**
```http
GET https://api.omni-torus.ngrok.app/scrape
```

### **🔹 Parameters:**
| Parameter      | Type   | Description |
|--------------|--------|-------------|
| `subreddits` | List[str] | List of subreddits to filter (e.g., `technology`, `ai`) |
| `keywords`   | List[str] | Keywords to search for in the title and content |
| `min_score`  | int    | Minimum upvotes required |
| `include_nsfw` | bool  | Whether to include NSFW posts (default: `false`) |
| `is_self`    | bool   | `true` for text posts, `false` for link posts, `null` for both |
| `flair`      | List[str] | List of allowed post flairs (case-insensitive) |
| `fetch_comments` | bool  | Whether to retrieve top-level comments (default: `false`) |
| `comments_limit` | int  | Number of top-level comments to fetch per post (default: `5`) |
| `sort_by`    | str    | Sorting method: `hot`, `new`, `top`, or `rising` |
| `limit`      | int    | Number of posts to retrieve (default: `10`) |

### **🔹 Example Request:**
```bash
curl -u your_username:your_password "https://api.omni-torus.ngrok.app/scrape?subreddits=technology&keywords=AI&limit=3"
```

### **🔹 Example Response:**
```json
{
    "posts": [
        {"id": "xyz", "title": "AI in 2024", "url": "https://reddit.com/r/technology/xyz"}
    ]
}
```

---

## **2️⃣ WebSocket API (Real-Time Subscription)**

The WebSocket API allows **real-time monitoring** of new Reddit posts matching specified filters.

### **🔹 Endpoint:**
```http
wss://api.omni-torus.ngrok.app/ws/subscribe
```

### **🔹 How to Connect:**
Using **wscat**:
```bash
wscat -c wss://api.omni-torus.ngrok.app/ws/subscribe -H "Authorization: Basic $(echo -n 'your_username:your_password' | base64)"
```

### **🔹 Subscription Request Format:**
After connecting to the WebSocket, send a JSON payload to **subscribe** to specific Reddit posts:
```json
{
    "subreddits": ["technology"],
    "keywords": ["AI"],
    "min_score": 5,
    "fetch_comments": true,
    "comments_limit": 5
}
```

### **🔹 Example Response (New Post Matches Subscription Criteria):**
```json
{
    "id": "abc123",
    "title": "Breakthrough in AI",
    "selftext": "A new AI model surpasses GPT-4.",
    "url": "https://reddit.com/r/technology/abc123",
    "score": 120,
    "subreddit": "technology",
    "flair": "AI",
    "num_comments": 15,
    "comments": [
        "This is amazing!",
        "What about ethical concerns?"
    ]
}
```

---

## **3️⃣ Managing Subscriptions**

- **To receive real-time updates**, stay connected to the WebSocket.
- **To stop receiving updates**, close the WebSocket connection.
- **To modify subscription filters**, disconnect and reconnect with a new request payload.

---

## **✅ Do it!**
The **Torus Reddit Scraper API** provides both **on-demand queries** via REST and **real-time subscriptions** via WebSocket. Use the appropriate method based on your needs.

---


# Self host Torus Reddit Scraper API 🚀
A FastAPI-based Reddit Scraper that provides real-time and on-demand Reddit data via REST API & WebSocket. This project is hosted on Azure, secured via ngrok with Basic Authentication, and designed for enterprise-level deployment.

## 📌 Features
🔹 FastAPI-based API for high-performance Reddit data scraping.
🔹 REST & WebSocket support for real-time & batch processing.
🔹 Authentication via ngrok Basic Auth (no need to modify FastAPI code).
🔹 Deployable on Azure VM with venv & tmux for stability.
🔹 Supports subreddit filtering, keyword matching, and comment extraction.
🔹 Runs in the background using tmux (persistent across SSH logouts).

## 🛠️ Installation & Setup
### 1️⃣ Clone the Repository
bash
Copy
Edit
git clone https://github.com/your-username/reddit-scraper-api.git
cd reddit-scraper-api

### 2️⃣ Setup Virtual Environment
bash
Copy
Edit
python3 -m venv venv
source venv/bin/activate

### 3️⃣ Install Dependencies
bash
Copy
Edit
pip install -r requirements.txt

### 4️⃣ Create a .env File
bash
Copy
Edit
nano .env
Add your Reddit API credentials:

ini
Copy
Edit
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
USER_AGENT=your_user_agent
Save & exit (Ctrl + X, then Y, then Enter).

### 5️⃣ Start FastAPI Server
bash
Copy
Edit
tmux new -s fastapi
source venv/bin/activate
uvicorn reddit_scraper_api:app --host 0.0.0.0 --port 4444 --reload
Detach from tmux: Ctrl + B, then D

## 🌎 Exposing API via ngrok
Run ngrok with Basic Authentication:

bash
Copy
Edit
tmux new -s ngrok
ngrok http 8000 --basic-auth="your_username:your_password"

🚀 Copy the ngrok URL, e.g., https://random-ngrok-url.ngrok.io, and use it for API requests.

## 🧪 API Testing
### 1️⃣ Test REST API
bash
Copy
Edit
curl -u your_username:your_password "https://random-ngrok-url.ngrok.io/scrape?subreddits=technology&keywords=AI&limit=3"

### 2️⃣ Test WebSocket API
Install wscat:

bash
Copy
Edit
npm install -g wscat
Connect to WebSocket:

bash
Copy
Edit
wscat -c wss://random-ngrok-url.ngrok.io/ws/subscribe

## 🛠️ Deployment & Auto-Start on Reboot
To keep the API running even after reboot, add this to crontab:

bash
Copy
Edit
crontab -e
Add:

less
Copy
Edit
@reboot tmux new -d -s fastapi 'cd ~/reddit_scraper && source venv/bin/activate && uvicorn reddit_scraper_api:app --host 0.0.0.0 --port 8000 --reload'
@reboot tmux new -d -s ngrok 'ngrok http 8000 --basic-auth="your_username:your_password"'

## 📄 License
This project is open-source under the MIT License.

## 👨‍💻 Contributors
@omni-robin - Creator & Maintainer

## 🚀 Future Improvements
✅ OAuth2/JWT-based authentication (instead of ngrok Basic Auth)
✅ Caching layer (Redis) for frequent queries
✅ Dockerized deployment for easy scaling

