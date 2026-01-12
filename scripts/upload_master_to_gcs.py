import os
import sys
from dotenv import load_dotenv
from google.cloud import storage

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import config

# Load env vars
load_dotenv()

def upload_master_list():
    """
    For Option B (Fresh Start), we still need the master list in the bucket
    so the pipeline knows which funds to download.
    This script uploads local data/isin_master_list.csv to gs://bucket/isin_master_list.csv
    """
    local_path = os.path.join(config.BASE_DIR, "data", "isin_master_list.csv")
    bucket_name = os.getenv('GCS_BUCKET_NAME')
    
    if not bucket_name:
        print("Error: GCS_BUCKET_NAME not set in environment or .env file.")
        return

    if not os.path.exists(local_path):
        print(f"Error: Local master list not found at {local_path}")
        return

    print(f"Uploading master list to bucket '{bucket_name}'...")
    
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob("isin_master_list.csv")
        
        blob.upload_from_filename(local_path)
        print("Success! Master list uploaded.")
        print("You can now run ./scripts/historical_setup.sh to populate the rest.")
        
    except Exception as e:
        print(f"Upload failed: {e}")

if __name__ == "__main__":
    upload_master_list()
