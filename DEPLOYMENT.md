# Google Cloud Deployment Guide

This guide covers deploying the NAV pipeline on Google Cloud Platform (GCP) with historical data stored on Google Cloud Storage.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Google Cloud Platform                 │
│                                                           │
│  ┌──────────────┐    ┌──────────────┐   ┌─────────────┐ │
│  │   Compute    │───▶│    Cloud     │   │   Cloud     │ │
│  │   Engine VM  │    │   Storage    │   │   SQL (PG)  │ │
│  │              │◀───│  (CSV files) │───│             │ │
│  │  - Pipeline  │    │              │   │  - NAV Data │ │
│  │  - Cron Jobs │    │  - NAV CSVs  │   │  - Returns  │ │
│  └──────────────┘    └──────────────┘   └─────────────┘ │
│         │                                                 │
│         ▼                                                 │
│  ┌──────────────┐                                        │
│  │  Cloud       │                                        │
│  │  Scheduler   │  (Alternative for cron)                │
│  └──────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

## 📦 Option 1: Google Cloud Storage (Recommended)

### Benefits
- ✅ Scalable storage for CSV files
- ✅ No need to manage disk space
- ✅ Automatic backups and versioning
- ✅ Share data across multiple VMs
- ✅ Lower cost than persistent disks

### Setup Cloud Storage

#### 1. Create Storage Bucket

```bash
# Set variables
PROJECT_ID="your-project-id"
BUCKET_NAME="nav-timeseries-data"
REGION="asia-south1"  # Mumbai

# Create bucket
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME/

# Create folder structure
gsutil -m mkdir gs://$BUCKET_NAME/historical_nav/
gsutil -m mkdir gs://$BUCKET_NAME/returns/
```

#### 2. Install Google Cloud Storage Library

Add to `requirements.txt`:
```
google-cloud-storage
```

Install:
```bash
pip install google-cloud-storage
```

#### 3. Update `config.py` for Cloud Storage

```python
import os
from google.cloud import storage

# Storage Configuration
USE_CLOUD_STORAGE = True  # Set to False for local storage
GCS_BUCKET_NAME = 'nav-timeseries-data'

# Base Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if USE_CLOUD_STORAGE:
    # Cloud Storage paths (GCS paths)
    NAV_DATA_DIR = f"gs://{GCS_BUCKET_NAME}"
    HISTORICAL_NAV_DIR = f"{NAV_DATA_DIR}/historical_nav"
    OUTPUT_DIR = f"{NAV_DATA_DIR}/returns"
    
    # Local temp directory for processing
    LOCAL_TEMP_DIR = "/tmp/navdata"
else:
    # Local file system paths
    NAV_DATA_DIR = os.path.join(BASE_DIR, "navdata")
    HISTORICAL_NAV_DIR = os.path.join(NAV_DATA_DIR, "historical_nav")
    OUTPUT_DIR = os.path.join(NAV_DATA_DIR, "returns")

# Files (will be in GCS or local based on USE_CLOUD_STORAGE)
ISIN_MASTER_LIST = f"{NAV_DATA_DIR}/isin_master_list.csv"
NAV_ALL_FILE = f"{NAV_DATA_DIR}/NAVAll.txt"
NAV_RETURNS_REPORT = f"{OUTPUT_DIR}/nav_returns_report.csv"

# Database
DB_URL = 'postgresql://postgres:password@your-cloudsql-ip:5432/mutualfundpro'
```

#### 4. Create GCS Helper Module

Create `gcs_utils.py`:

```python
from google.cloud import storage
import os
import config

class GCSStorage:
    """Helper class for Google Cloud Storage operations"""
    
    def __init__(self):
        self.client = storage.Client()
        self.bucket = self.client.bucket(config.GCS_BUCKET_NAME)
    
    def upload_file(self, local_path, gcs_path):
        """Upload file to GCS"""
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)
        print(f"Uploaded {local_path} to gs://{config.GCS_BUCKET_NAME}/{gcs_path}")
    
    def download_file(self, gcs_path, local_path):
        """Download file from GCS"""
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob = self.bucket.blob(gcs_path)
        blob.download_to_filename(local_path)
        print(f"Downloaded gs://{config.GCS_BUCKET_NAME}/{gcs_path} to {local_path}")
    
    def list_files(self, prefix):
        """List files in GCS with given prefix"""
        blobs = self.bucket.list_blobs(prefix=prefix)
        return [blob.name for blob in blobs]
    
    def file_exists(self, gcs_path):
        """Check if file exists in GCS"""
        blob = self.bucket.blob(gcs_path)
        return blob.exists()
    
    def read_csv(self, gcs_path):
        """Read CSV directly from GCS"""
        import pandas as pd
        blob = self.bucket.blob(gcs_path)
        content = blob.download_as_string()
        return pd.read_csv(pd.io.common.BytesIO(content))
    
    def write_csv(self, df, gcs_path):
        """Write DataFrame to GCS as CSV"""
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_string(df.to_csv(index=False), content_type='text/csv')

# Usage example
if config.USE_CLOUD_STORAGE:
    storage = GCSStorage()
else:
    storage = None
```

#### 5. Update Pipeline to Use GCS

Modify `nav_manager.py` to handle GCS:

```python
import config
from gcs_utils import GCSStorage

class NavManager:
    def __init__(self):
        if config.USE_CLOUD_STORAGE:
            self.storage = GCSStorage()
        # ... rest of init
    
    def save_nav_data(self, df, scheme_code):
        """Save NAV data (GCS or local)"""
        if config.USE_CLOUD_STORAGE:
            gcs_path = f"historical_nav/{scheme_code}.csv"
            self.storage.write_csv(df, gcs_path)
        else:
            filepath = f"{config.HISTORICAL_NAV_DIR}/{scheme_code}.csv"
            df.to_csv(filepath, index=False)
```

## 🖥️ Option 2: Deploy on Google Compute Engine (Budget-Friendly)

### Recommended: e2-micro Instance

**Best for NAV pipeline:**
- **e2-micro**: $6-7/month (0.25 GB RAM, shared CPU)
- Perfect for daily cron jobs
- Stops when idle (can schedule start/stop)

### 1. Create Cheap VM Instance

```bash
# Option A: e2-micro (Cheapest - $6-7/month)
gcloud compute instances create nav-pipeline-vm \
    --project=$PROJECT_ID \
    --zone=asia-south1-a \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB \
    --boot-disk-type=pd-standard \
    --scopes=https://www.googleapis.com/auth/cloud-platform

# Option B: f1-micro (Free tier eligible - first 730 hours/month)
# Note: Only 1 f1-micro in us-west1, us-central1, or us-east1 is free
gcloud compute instances create nav-pipeline-vm \
    --project=$PROJECT_ID \
    --zone=us-central1-a \
    --machine-type=f1-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB \
    --boot-disk-type=pd-standard \
    --scopes=https://www.googleapis.com/auth/cloud-platform

# Option C: e2-small (Better performance - $14/month)
gcloud compute instances create nav-pipeline-vm \
    --project=$PROJECT_ID \
    --zone=asia-south1-a \
    --machine-type=e2-small \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-standard \
    --scopes=https://www.googleapis.com/auth/cloud-platform
```

### 2. SSH into VM

```bash
gcloud compute ssh nav-pipeline-vm --zone=asia-south1-a
```

### 3. Setup on VM

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3
sudo apt-get install -y python3 python3-pip git

# Clone repository
git clone <your-repo-url>
cd navtimeseries

# Install dependencies
pip3 install -r requirements.txt

# Setup authentication for GCS
gcloud auth application-default login

# Or use service account (better for production)
# gcloud auth activate-service-account --key-file=/path/to/key.json
```

### 4. Configure Database Access

```bash
# Edit config.py
nano config.py

# Update DB_URL with Cloud SQL connection
# Format: postgresql://user:password@CLOUD_SQL_IP:5432/database
```

### 5. Setup Cron Jobs on VM

```bash
crontab -e

# Add daily sync at 6 PM IST
0 18 * * * cd /home/username/navtimeseries && ./daily_sync.sh
```

## ☁️ Option 3: Cloud Scheduler + Cloud Functions (Serverless)

### Benefits
- No VM management
- Pay only for execution time
- Auto-scaling

### Setup Cloud Function

Create `main.py` for Cloud Function:

```python
import functions_framework
from main import main as run_pipeline

@functions_framework.http
def nav_pipeline_trigger(request):
    """HTTP Cloud Function to trigger NAV pipeline"""
    try:
        run_pipeline()
        return {"status": "success", "message": "Pipeline completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500
```

Deploy:
```bash
gcloud functions deploy nav-pipeline \
    --runtime python39 \
    --trigger-http \
    --allow-unauthenticated \
    --timeout=540s \
    --memory=2048MB
```

Create Cloud Scheduler job:
```bash
gcloud scheduler jobs create http nav-daily-sync \
    --schedule="0 18 * * *" \
    --uri="https://REGION-PROJECT_ID.cloudfunctions.net/nav-pipeline" \
    --http-method=POST
```

## 🔐 Security & Access

### Service Account Setup

```bash
# Create service account
gcloud iam service-accounts create nav-pipeline-sa \
    --display-name="NAV Pipeline Service Account"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:nav-pipeline-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:nav-pipeline-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudsql.client"

# Download key
gcloud iam service-accounts keys create key.json \
    --iam-account=nav-pipeline-sa@$PROJECT_ID.iam.gserviceaccount.com
```

Use in application:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

## 📊 Migration: Local to Cloud Storage

### Migrate Existing NAV Files

```bash
# Upload existing CSV files to GCS
gsutil -m cp -r navdata/historical_nav/*.csv gs://$BUCKET_NAME/historical_nav/
gsutil -m cp -r navdata/returns/*.csv gs://$BUCKET_NAME/returns/

# Upload master list
gsutil cp navdata/isin_master_list.csv gs://$BUCKET_NAME/
```

### Hybrid Approach (Transition Period)

Keep local copies while testing GCS:

```python
# config.py
BACKUP_LOCAL_FILES = True  # Save to both local and GCS during transition

# In nav_manager.py
def save_nav_data(self, df, scheme_code):
    # Save to GCS
    if config.USE_CLOUD_STORAGE:
        gcs_path = f"historical_nav/{scheme_code}.csv"
        self.storage.write_csv(df, gcs_path)
    
    # Also save locally if backup enabled
    if config.BACKUP_LOCAL_FILES:
        filepath = f"navdata/historical_nav/{scheme_code}.csv"
        df.to_csv(filepath, index=False)
```

## 💰 Cost Estimation (Updated for Budget Options)

### Monthly Costs - **CHEAPEST Setup**

**Storage (Cloud Storage)**
- 10 GB of CSV files: $0.20/month
- Operations (read/write): $0.10/month
- **Total Storage: ~$0.30/month**

**Compute (e2-micro VM - Recommended)**
- VM running 24/7: ~$6.50/month
- 20 GB persistent disk: ~$0.80/month
- **Total Compute: ~$7.30/month**

**Grand Total: ~$7.60/month** (excluding Cloud SQL)

---

### Cost Comparison Table

| Option | Monthly Cost | Notes |
|--------|-------------|-------|
| **e2-micro** (Cheapest) | **~$7.60** | Perfect for daily jobs, 0.25 GB RAM |
| **f1-micro** (Free tier) | **$0.30-$2** | Free if in eligible region, 0.60 GB RAM |
| e2-small | ~$14.50 | Better performance, 2 GB RAM |
| e2-medium | ~$26.50 | High performance, 4 GB RAM |
| Cloud Functions | ~$0.40 | Serverless, best for infrequent runs |

**Recommended: e2-micro** for best balance of cost and reliability.

---

### 🎯 Further Cost Optimization

#### 1. **Use Scheduled Start/Stop**

Auto-stop VM when not needed:

```bash
# Stop VM at night (11 PM)
0 23 * * * gcloud compute instances stop nav-pipeline-vm --zone=asia-south1-a

# Start VM in morning (8 AM)
0 8 * * * gcloud compute instances start nav-pipeline-vm --zone=asia-south1-a
```

**Savings**: Run only 12 hours/day = **50% cost reduction** → $3.25/month!

#### 2. **Use Preemptible VM**

Save 60-80% on compute:

```bash
gcloud compute instances create nav-pipeline-vm \
    --machine-type=e2-micro \
    --preemptible \
    --zone=asia-south1-a
```

**Cost**: ~$2/month (but may be terminated anytime)

#### 3. **Free Tier Optimization**

Use f1-micro in free tier regions:
- Region: `us-central1`, `us-west1`, or `us-east1`
- 1 f1-micro instance = FREE (first 730 hours/month)
- **Cost**: $0.30/month (only storage!)

#### 4. **Run Only During Market Hours**

Start VM at 9 AM, stop at 7 PM:
- Run: ~10 hours/day × 22 trading days = 220 hours/month
- **Cost**: ~$2/month for compute + $0.30 storage = **$2.30/month**

---

### 🏆 **Absolute Cheapest Setup**

```
f1-micro VM (us-central1) + Cloud Storage
Monthly Cost: $0.30 - $2.00
```

Setup:
```bash
# Create in free tier region
gcloud compute instances create nav-pipeline-vm \
    --zone=us-central1-a \
    --machine-type=f1-micro \
    --boot-disk-size=10GB \
    --scopes=cloud-platform

# Use Cloud Storage for CSV files
# Setup daily cron at 6 PM
```

**Total Annual Cost**: ~$3.60 - $24/year 🎉

## 🚀 Recommended Deployment (Budget-Friendly)

### For Production - Cheapest Option

```
1. Store CSV files on Cloud Storage (scalable, $0.30/month)
2. Use e2-micro Compute Engine VM ($6.50/month)
3. Setup cron jobs on VM
4. Use service account authentication
5. Enable Cloud Logging for monitoring

Total: ~$7.60/month
```

### Alternative: Free Tier Setup

```
1. Store CSV files on Cloud Storage
2. Use f1-micro VM in us-central1 (FREE)
3. Setup cron jobs
4. Minimize disk size (10 GB)

Total: ~$0.30/month (only storage!)
```

### Deployment Steps (e2-micro)

```bash
# 1. Create GCS bucket
gsutil mb -l asia-south1 gs://nav-timeseries-data

# 2. Upload code to GitHub/Cloud Source Repositories

# 3. Create e2-micro VM (CHEAPEST)
gcloud compute instances create nav-pipeline-vm \
    --machine-type=e2-micro \
    --zone=asia-south1-a \
    --boot-disk-size=20GB \
    --scopes=cloud-platform

# 4. SSH and setup
gcloud compute ssh nav-pipeline-vm
git clone <repo>
cd navtimeseries
pip3 install -r requirements.txt

# 5. Configure
nano config.py  # Set USE_CLOUD_STORAGE=True, DB_URL

# 6. Initial data load
./historical_setup.sh

# 7. Setup cron
crontab -e
# Add: 0 18 * * * cd ~/navtimeseries && ./daily_sync.sh

# 8. Monitor
tail -f logs/daily_sync_*.log
```

### Deployment Steps (f1-micro - FREE)

```bash
# Same as above, but use this VM creation:
gcloud compute instances create nav-pipeline-vm \
    --machine-type=f1-micro \
    --zone=us-central1-a \
    --boot-disk-size=10GB \
    --scopes=cloud-platform
```

## 📝 Configuration Summary

**`config.py` for GCP:**
```python
USE_CLOUD_STORAGE = True
GCS_BUCKET_NAME = 'nav-timeseries-data'
DB_URL = 'postgresql://user:pass@CLOUDSQL_IP:5432/db'
```

**Environment Variables:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

## 🔍 Monitoring

### Cloud Logging

View logs:
```bash
gcloud logging read "resource.type=gce_instance AND resource.labels.instance_id=<INSTANCE_ID>" --limit 50
```

### Cloud Monitoring

Create alerts for:
- Pipeline failures
- Database connection issues
- Storage quota exceeded

## 📚 Additional Resources

- [Google Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [Compute Engine Documentation](https://cloud.google.com/compute/docs)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)
- [Cloud Scheduler Documentation](https://cloud.google.com/scheduler/docs)
