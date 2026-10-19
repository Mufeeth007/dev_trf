# Developer Activity Tracker

A complete, beginner-friendly full-stack **Developer Activity Tracker** web application built with **Python Flask**, **FerretDB** (as the permanent document database using `pymongo`), and **Redis** (as the high-speed caching layer using `redis`).

---

## 📌 Architecture Overview

```
                      +-----------------------------------+
                      |   Browser Frontend (HTML/CSS/JS)   |
                      |   Responsive Dashboard & Controls |
                      +-----------------+-----------------+
                                        |  REST API (JSON)
                                        v
                      +-----------------+-----------------+
                      |       Python Flask Backend        |
                      |   Routes, Validation, Business    |
                      +--------+--------------------+-----+
                               |                    |
                  (Cache Hit / Invalidation)   (Permanent Storage)
                               |                    |
                               v                    v
                      +--------+---------+  +-------+----------+
                      |   Redis Cache    |  |     FerretDB     |
                      | (TTL: 60s, Stats |  | (MongoDB Protocol|
                      |   & Activities)  |  |   via pymongo)   |
                      +------------------+  +-------+----------+
                                                    |
                                                    v
                                            +-------+----------+
                                            | PostgreSQL / SQL |
                                            | (FerretDB Engine)|
                                            +------------------+
```

1. **FerretDB (Primary Storage)**:
   - Stores all activity records permanently in a database named `developer_tracker` and collection `activities`.
   - Communicates using standard MongoDB wire protocol via `pymongo`.
   - Translates MongoDB queries into SQL queries on its PostgreSQL or SQLite backend.
   - FerretDB is the permanent single source of truth.
2. **Redis (Cache Layer)**:
   - Caches recently queried activity lists and summary statistics.
   - Default cache expiration (TTL) is **60 seconds**.
   - Invalidates relevant cached keys immediately whenever activities are created, edited, or deleted.
   - **Graceful degradation**: If Redis is offline, the application continues to operate smoothly using FerretDB directly.
3. **Frontend (Vanilla HTML, CSS, JavaScript)**:
   - Responsive dashboard featuring summary cards, quick filters, debounced search, sort controls, add/edit form, delete confirmation modal, and real-time database/cache health status badges.

---

## 🛠️ Technologies Used

| Layer | Technology | Description |
|---|---|---|
| **Frontend** | HTML5, CSS3, JavaScript (ES6+) | Vanilla, responsive, no React or Tailwind |
| **Backend** | Python Flask (3.x) | Modular REST API and template rendering |
| **Primary Database** | FerretDB | MongoDB-compatible document database |
| **DB Driver** | `pymongo` | Standard Python MongoDB driver |
| **Cache Layer** | Redis | In-memory key-value cache (TTL 60s) |
| **Cache Driver** | `redis-py` | Python Redis client |
| **Environment** | `python-dotenv` | Config loader for `.env` |

---

## 📁 Project Structure

```
developer-activity-tracker/
│
├── app.py                  # Flask server and REST API endpoints
├── config.py               # Configuration and environment variable loader
├── ferretdb_client.py      # FerretDB connection and CRUD operations (pymongo)
├── redis_cache.py          # Redis caching operations and invalidation logic
├── requirements.txt        # Python package dependencies
├── .env.example            # Sample environment variables template
├── .env                    # Local environment variables file (git ignored)
├── .gitignore              # Files excluded from version control
├── docker-compose.yml      # Optional 1-command startup for FerretDB + Redis
├── README.md               # Beginner-friendly setup and usage guide
│
├── templates/
│   └── index.html          # Dashboard HTML template
│
└── static/
    ├── style.css           # Modern custom CSS styles
    └── script.js           # Frontend interactivity, API calls, and validation
```

---

## 📋 Prerequisites

Before running the application, make sure you have:
1. **Windows 10 / 11** (PowerShell)
2. **Python 3.10+** installed
3. **Redis Server** installed and running
4. **FerretDB** installed and running with its PostgreSQL or SQLite backend

---

## 🚀 Step-by-Step Setup Instructions

### Step 1: Install Python on Windows

1. Download the latest Python 3 installer from the official website:
   👉 [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Run the installer.
   > **IMPORTANT**: Check the box that says **"Add python.exe to PATH"** before clicking **Install Now**.
3. Verify Python installation in PowerShell:
   ```powershell
   python --version
   pip --version
   ```

---

### Step 2: Install and Start Redis on Windows

You have two simple options for running Redis on Windows:

#### Option A: Native Windows Redis Service (Recommended)
1. Download Redis for Windows from the GitHub release:
   👉 [https://github.com/microsoftarchive/redis/releases](https://github.com/microsoftarchive/redis/releases) or use **Memurai** (Redis-compatible for Windows) from [https://www.memurai.com/](https://www.memurai.com/).
2. Run the installer, which sets up Redis as a Windows Service running automatically on port `6379`.
3. To verify Redis is running in PowerShell:
   ```powershell
   Get-Service *redis*
   ```
4. If installed via binary without service:
   ```powershell
   redis-server.exe
   ```

#### Option B: Run Redis via Docker
```powershell
docker run -d --name tracker-redis -p 6379:6379 redis:7-alpine
```

Test the Redis connection:
```powershell
# In PowerShell:
Test-NetConnection -ComputerName 127.0.0.1 -Port 6379
```

---

### Step 3: Install and Start FerretDB with its Backend

> **About FerretDB**:
> FerretDB translates MongoDB wire protocol commands into SQL queries. To run, FerretDB requires an underlying SQL backend—most commonly **PostgreSQL** or **SQLite**.
>
> Applications connect to FerretDB on port `27017` using standard MongoDB connection strings (`mongodb://127.0.0.1:27017/`).

#### Option A: Quickest Method — Docker Compose (Recommended)
The project includes a `docker-compose.yml` file that starts both FerretDB (with PostgreSQL) and Redis in one command:

```powershell
# From the project root directory:
docker compose up -d
```

This starts:
- `ferretdb-postgres` on internal port `5432` (mapped to `5433` on host).
- `ferretdb` on port `27017` (MongoDB-compatible wire protocol).
- `tracker-redis` on port `6379`.

To check running containers:
```powershell
docker ps
```

#### Option B: Standalone FerretDB with PostgreSQL (Docker)
1. Run PostgreSQL:
   ```powershell
   docker run -d --name ferretdb-pg -p 5432:5432 -e POSTGRES_DB=ferretdb -e POSTGRES_USER=ferretdb -e POSTGRES_PASSWORD=ferretdb_password postgres:16-alpine
   ```
2. Run FerretDB:
   ```powershell
   docker run -d --name ferretdb -p 27017:27017 -e FERRETDB_POSTGRESQL_URL="postgres://ferretdb:ferretdb_password@host.docker.internal:5432/ferretdb" ghcr.io/ferretdb/ferretdb:latest
   ```

#### Option C: FerretDB Binary with SQLite Backend (No Docker required)
1. Download the FerretDB Windows binary from [https://github.com/FerretDB/FerretDB/releases](https://github.com/FerretDB/FerretDB/releases).
2. Run FerretDB pointing to a local SQLite database:
   ```powershell
   .\ferretdb.exe --sqlite-url="file:ferretdb.sqlite?mode=rwc" --listen-addr="127.0.0.1:27017"
   ```

Test that FerretDB is listening on port `27017`:
```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 27017
```

---

### Step 4: Open the Project in VS Code

1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd d:\Projects\dev_trf
   ```
2. Open VS Code in this directory:
   ```powershell
   code .
   ```
3. Open an integrated PowerShell terminal inside VS Code by pressing ``Ctrl + ` `` (Backtick) or selecting **Terminal > New Terminal**.

---

### Step 5: Create and Activate Python Virtual Environment

1. In PowerShell inside the project directory, create a virtual environment named `venv`:
   ```powershell
   python -m venv venv
   ```
2. If PowerShell script execution is restricted on your machine, enable it for your current user:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
3. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   *(You will see `(venv)` appear at the beginning of your PowerShell prompt).*

---

### Step 6: Install Required Packages

With the virtual environment activated, install the required packages:

```powershell
pip install -r requirements.txt
```

Verify that all packages installed properly:
```powershell
pip list
```

---

### Step 7: Configure the `.env` File

1. Check that a `.env` file exists in the project root. If not, copy it from `.env.example`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Open `.env` and verify the settings:
   ```ini
   # FerretDB Connection URI (MongoDB wire protocol compatible)
   FERRETDB_URI=mongodb://127.0.0.1:27017/
   FERRETDB_DB_NAME=developer_tracker
   FERRETDB_COLLECTION_NAME=activities

   # Redis Connection URL
   REDIS_URL=redis://127.0.0.1:6379/0

   # Cache Expiration Time in seconds
   CACHE_TTL=60

   # Flask Server Settings
   HOST=127.0.0.1
   PORT=5000
   FLASK_DEBUG=True
   ```
   > **Note**: If your FerretDB or Redis instances use different ports, hostnames, or authentication, adjust these variables accordingly.

---

### Step 8: Run the Flask Application

Run the application using Python:

```powershell
python app.py
```

You will see output similar to:
```
Starting Developer Activity Tracker on http://127.0.0.1:5000
FerretDB target: mongodb://127.0.0.1:27017/ (Database: developer_tracker)
Redis target: redis://127.0.0.1:6379/0 (TTL: 60s)
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

---

### Step 9: Open the Website in a Browser

1. Open your web browser (Chrome, Edge, Firefox).
2. Navigate to:
   👉 **`http://127.0.0.1:5000`**
3. You will see the **Developer Activity Tracker** dashboard!

---

## 🎯 How to Use the Application

### 1. Adding an Activity
1. Locate the **"Add New Activity"** form on the left.
2. Fill in:
   - **Project Name**: e.g., `Authentication Service`
   - **Activity Title**: Select from preset suggestions or type your own (e.g., `Database created`, `Bug fixed`).
   - **Developer Name**: e.g., `Sarah Chen`
   - **Status**: Choose `Success`, `Pending`, or `Failed`.
   - **Description**: Add brief details of what was done.
3. Click **"Record Activity"**.
4. The activity is permanently saved in FerretDB, the Redis cache is cleared, and the table updates instantly.

### 2. Searching and Filtering
- **Search bar**: Type any project name, title, or developer name to instantly filter activities.
- **Status filter**: Select `All Statuses`, `Success`, `Pending`, or `Failed` from the dropdown.
- **Sort By**: Toggle between `Newest First` and `Oldest First`.

### 3. Editing an Activity
1. Click the **✏️ Edit** button on any table row.
2. The form pre-fills with the activity details and turns into **"Edit Activity"** mode.
3. Make your updates and click **"Update Activity"**.
4. To cancel without saving, click **"Cancel Edit"**.

### 4. Deleting an Activity
1. Click the **🗑️ Delete** button on any row.
2. A confirmation modal will appear with details of the activity.
3. Click **"Delete Activity"** to confirm permanent removal from FerretDB.

### 5. Observing the Redis Cache Layer
- Watch the badge above the table:
  - `⚡ Redis Cached (TTL 60s)`: Indicates the current list query was served directly from memory via Redis.
  - `🗄️ FerretDB Direct`: Indicates the query fetched fresh data from FerretDB (e.g. after a cache miss or cache invalidation).
- When you add, edit, or delete an activity, Redis automatically invalidates stale keys, ensuring the next read fetches fresh data from FerretDB.

---

## 📡 REST API Reference

| Method | Endpoint | Description | Cache Behavior |
|---|---|---|---|
| `GET` | `/` | Web dashboard page | N/A |
| `GET` | `/api/health` | Check App, FerretDB, and Redis status | Direct Ping |
| `GET` | `/api/dashboard/stats` | Activity counts (total, success, pending, failed) | Cached (TTL 60s) |
| `GET` | `/api/activities` | List activities (`?search=&status=&sort=`) | Cached (TTL 60s) |
| `GET` | `/api/activities/<id>` | Fetch single activity by ID | Cached (TTL 60s) |
| `POST` | `/api/activities` | Create new activity | Invalidates Cache |
| `PUT` | `/api/activities/<id>` | Update existing activity | Invalidates Cache |
| `DELETE`| `/api/activities/<id>` | Delete activity | Invalidates Cache |

### Example Activity Payload (`POST /api/activities`):
```json
{
  "project_name": "Payment Gateway API",
  "title": "Bug fixed",
  "developer_name": "Alex Morgan",
  "status": "Success",
  "description": "Resolved webhook signature validation edge case for stripe events."
}
```

---

## ❓ Troubleshooting & FAQs

### Q: Why does the FerretDB status badge show "Offline"?
1. Verify that FerretDB is running and listening on port `27017`:
   ```powershell
   Test-NetConnection -ComputerName 127.0.0.1 -Port 27017
   ```
2. Make sure FerretDB's underlying database (e.g. PostgreSQL or SQLite) is also running and accessible to FerretDB.
3. Check the `FERRETDB_URI` in your `.env` file.

### Q: What happens if Redis is offline?
- The application automatically switches to **graceful degradation** mode.
- The Redis badge in the header will display `Offline (Bypassed)`.
- All CRUD operations continue functioning normally directly through FerretDB without crashing.

### Q: Can I run this without Docker?
- **Yes!** You can run native Redis on Windows (e.g. Memurai or Microsoft Redis archive), and the standalone `ferretdb.exe` with SQLite backend:
  ```powershell
  .\ferretdb.exe --sqlite-url="file:ferretdb.sqlite?mode=rwc" --listen-addr="127.0.0.1:27017"
  ```
