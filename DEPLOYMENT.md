# Deployment Guide

This guide covers three different ways to deploy the NAV Time Series Pipeline. Choose the one that best fits your needs.

## 📋 Prerequisites (Common)

1.  **Google Cloud Project** with Billing enabled.
2.  **Service Account** with permissions:
    - `Storage Object Admin` (if using GCS)
    - `Cloud SQL Client`
3.  **Database**: A PostgreSQL instance (Cloud SQL or other).

---

## 📦 Option 1: Docker (Recommended)

This is the most robust method. It packages the application and its environment into a container, ensuring consistency.

### 1. Build the Image

```bash
docker build -t nav-pipeline .
```

### 2. Push to Registry (GCR/Artifact Registry)

```bash
gcloud auth configure-docker
docker tag nav-pipeline gcr.io/[PROJECT-ID]/nav-pipeline:latest
docker push gcr.io/[PROJECT-ID]/nav-pipeline:latest
```

### 3. Deploy to VM

1.  Create a **Compute Engine VM** (e.g., `e2-micro`).
2.  Select **"Deploy a container image"**.
3.  Image: `gcr.io/[PROJECT-ID]/nav-pipeline:latest`
4.  **Environment Variables**:
    - `USE_GCS`: `True` (Recommended) or `False`
    - `GCS_BUCKET_NAME`: `your-bucket-name`
    - `DB_URL`: `postgresql://...`
5.  **Mount Volume** (If NOT using GCS):
    - Mount a host path to `/app/data` to persist CSVs.

---

## 🖥️ Option 2: Direct VM (Traditional)

This involves manually setting up the environment on a VM. Good for simple, low-cost setups without Docker overhead.

### 1. Provision VM

Create an `e2-micro` instance on Google Compute Engine.

### 2. Setup Environment

SSH into the VM:

```bash
sudo apt-get update && sudo apt-get install -y python3 python3-pip git
git clone <your-repo-url>
cd navtimeseries
pip3 install -r requirements.txt
```

### 3. Configure

Edit `app/config.py` or set environment variables in `~/.bashrc`:

```bash
export USE_GCS=True
export GCS_BUCKET_NAME=your-bucket-name
export DB_URL=postgresql://...
```

### 4. Setup Cron

Run `crontab -e` and add:

```bash
0 18 * * * cd /home/your-user/navtimeseries && ./scripts/daily_sync.sh >> /var/log/nav_cron.log 2>&1
```

---

## ☁️ Option 3: Serverless (Advanced)

Use Cloud Scheduler + Cloud Run (or Cloud Functions) to run the pipeline only when needed. This is the most cost-effective for infrequent jobs.

### 1. Containerize for Cloud Run

Use the same Docker image as Option 1.

### 2. Deploy to Cloud Run

```bash
gcloud run deploy nav-pipeline-job \
    --image gcr.io/[PROJECT-ID]/nav-pipeline:latest \
    --set-env-vars USE_GCS=True,GCS_BUCKET_NAME=...,DB_URL=... \
    --platform managed \
    --region us-central1
```

_Note: You might need to adjust the `CMD` in Dockerfile to run the script once and exit, rather than running `cron`._

### 3. Schedule with Cloud Scheduler

Create a job to trigger the Cloud Run service:

```bash
gcloud scheduler jobs create http nav-daily-trigger \
    --schedule "0 18 * * *" \
    --uri "https://[CLOUD-RUN-URL]" \
    --http-method POST
```

---

## 🗄️ Storage Strategy: Local vs. GCS

The application now supports Google Cloud Storage (GCS) natively.

### A. Local Storage (Default)

- **Config**: `USE_GCS = False`
- **Pros**: Fast, simple, free (uses VM disk).
- **Cons**: Data is lost if VM/Container is deleted (unless volumes are mounted).

### B. Google Cloud Storage (Recommended for Prod)

- **Config**: `USE_GCS = True`
- **Pros**: Persistent, versioned, accessible from anywhere (VM, Cloud Run, Local).
- **Setup**:
  1.  Create a bucket: `gsutil mb gs://your-bucket-name`
  2.  Set `GCS_BUCKET_NAME` env var.
  3.  Ensure your VM/Service Account has `Storage Object Admin` role.
