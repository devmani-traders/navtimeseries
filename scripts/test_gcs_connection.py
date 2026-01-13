import os
import sys
from google.cloud import storage
from google.api_core.exceptions import Forbidden, NotFound

def test_gcs_connection():
    bucket_name = os.getenv('GCS_BUCKET_NAME', 'nav-timeseries-data')
    use_gcs = os.getenv('USE_GCS', 'False').lower() == 'true'
    
    print("="*60)
    print("GCS CONFIGURATION CHECK")
    print("="*60)
    print(f"USE_GCS env var: {os.getenv('USE_GCS')} (parsed as {use_gcs})")
    print(f"GCS_BUCKET_NAME: {bucket_name}")
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
    print("-" * 60)

    if not use_gcs:
        print("WARNING: USE_GCS is not set to 'true'. The app will use local storage.")
        print("To enable GCS, run:")
        print("  export USE_GCS=true")
        print("-" * 60)

    try:
        print(f"Attempting to connect to GCS bucket '{bucket_name}'...")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        
        # Check if bucket exists and we have access
        if not bucket.exists():
            print(f"ERROR: Bucket '{bucket_name}' does not exist or you don't have permission to view it.")
            return False
            
        print("SUCCESS: Connected to bucket!")
        
        # Try listing blobs (to verify permissions)
        blobs = list(bucket.list_blobs(max_results=5))
        print(f"Successfully listed {len(blobs)} files (sample).")
        
        print("\nReady to go! Your GCS setup looks correct.")
        return True
        
    except Exception as e:
        print(f"\nERROR: Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure GOOGLE_APPLICATION_CREDENTIALS points to a valid JSON key file.")
        print("2. Ensure the Service Account has 'Storage Object Admin' role.")
        print("3. Ensure the bucket name is correct.")
        return False

if __name__ == "__main__":
    test_gcs_connection()
