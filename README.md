# NAV Time Series Pipeline

A comprehensive Python pipeline for downloading, processing, and managing Indian mutual fund NAV (Net Asset Value) data. 
Now fully dockerized and supports Google Cloud Storage (GCS) for scalable deployment.

## 🌟 Features

- 📥 **Automated NAV Data Download** - Downloads historical NAV data from AMFI India/API
- ☁️ **Google Cloud Storage** - Seamlessly stores data in GCS buckets
- 🐳 **Dockerized** - Ready for VM deployment with one-time setup and daily cron modes
- 🔄 **Hybrid Update Strategy** - Efficient daily updates using NAVAll.txt with API fallback
- 📊 **Returns Calculation** - Computes absolute and CAGR returns (1M, 1Y, 3Y, 5Y, etc.)
- 🗄️ **PostgreSQL Integration** - Syncs NAV history and returns to your database

## 🚀 Deployment (VM / Docker)

This is the recommended way to run the application.

### 1. Prerequisites
- Docker installed
- Google Cloud Service Account (with `Storage Object Admin` role) attached to the VM

### 2. Configuration (`.env`)
Create a `.env` file in your root directory:
```bash
# Database
DB_URL=postgresql://user:pass@host:port/database

# Storage Mode (Set to true for Cloud)
USE_GCS=true
GCS_BUCKET_NAME=your-gcs-bucket-name

# (Optional) Only needed if NOT using VM Identity
# GOOGLE_APPLICATION_CREDENTIALS=/app/gcs-key.json
```

### 3. Quick Start Commands (Run on VM)

You can perform all key operations using the Docker image. 
*Note: We assume your config file on the VM is named `nav.env`.*

#### Step 1: Build Image (On Local Machine)
```bash
docker build -t nav-pipeline .
```

#### Step 2: One-Time Historical Setup
*Run this once when you set up.*
1.  **Download**: It checks GCS. If empty, it downloads 10 years of history and uploads to your GCS bucket.
2.  **Sync**: It reads those files from GCS and bulk-inserts them into your DB.

Run in background so it doesn't stop if you disconnect:
```bash
docker run -d --name nav-setup --env-file nav.env nav-pipeline setup
```

Watch the logs:
```bash
docker logs -f nav-setup
```

Once finished (Status: `Exited (0)`), remove the container:
```bash
docker rm nav-setup
```

#### Step 3: Start Daily Sync (Daemon)
*Keep this running forever.*
Starts a background cron job that updates data every day at 18:00 UTC.
```bash
docker run -d --name nav-daily-sync --env-file nav.env --restart unless-stopped nav-pipeline cron
```

#### Step 4: Refresh Master List
*Run this whenever you add new funds to DB.*
Refreshes the master list in GCS based on your Database funds.
```bash
docker run --rm --env-file nav.env nav-pipeline refresh-master
```

### 4. Monitoring & Logs

**Check Daily Sync Logs (Cron Job)**
Since the daily sync runs in the background, check the internal cron log:
```bash
docker exec nav-daily-sync tail -f /var/log/cron.log
```

**Check Historical Setup Logs**
If the standard logs seem stuck, check the detailed internal log:
```bash
docker exec nav-setup sh -c "tail -f /app/logs/*.log"
```

**Check Container Status**
```bash
docker ps
```
---

## 🛠️ Local Development (Manual)

If you want to run scripts manually without Docker:

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Scripts
```bash
# Initialize Historical Data
./scripts/historical_setup.sh

# Run Daily Sync
./scripts/daily_sync.sh
```

## 📁 Project Structure

```
navtimeseries/
├── app/                        # Main Application Package
│   ├── config.py               # Configuration (Env + logic)
│   ├── main.py                 # Pipeline Entry Point
│   ├── services/               # Core Logic (NavManager, ReturnCalculator)
│   ├── database/               # Database Sync Logic
│   └── utils/                  # Storage Abstraction (Local vs GCS)
├── scripts/                    # Helper Scripts
│   ├── historical_setup.sh     # Orchestrator for Setup
│   ├── daily_sync.sh           # Orchestrator for Daily Job
│   ├── populate_master_from_db.py # Syncs DB -> Master CSV
│   └── upload_master_to_gcs.py # (Internal) Upload utility
├── entrypoint.sh               # Docker Entrypoint
├── Dockerfile                  # Docker Build config
└── requirements.txt
```

## 📊 Data Flow

### Daily Update Process
1.  **Cron** wakes up at 18:00 UTC.
2.  **Download**: Fetches latest `NAVAll.txt` from AMFI.
3.  **Process**: Updates each fund's CSV in GCS (incremental append).
4.  **Calculate**: Re-computes returns (1M, 1Y, CAGR, etc.).
5.  **Sync**: Pushes new NAVs and Returns to PostgreSQL.

### Adding New Funds
1.  Insert new Fund ISIN into your PostgreSQL `mf_fund` table.
2.  Run `docker run ... refresh-master`
3.  The pipeline will pick up the new fund in the next Daily Sync cycle.
