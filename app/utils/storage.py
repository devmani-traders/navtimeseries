import os
import pandas as pd
from io import StringIO, BytesIO
from app import config

class StorageManager:
    def __init__(self):
        self.use_gcs = config.USE_GCS
        if self.use_gcs:
            from google.cloud import storage
            self.client = storage.Client()
            self.bucket = self.client.bucket(config.GCS_BUCKET_NAME)

    def exists(self, path):
        if self.use_gcs:
            blob = self.bucket.blob(path)
            return blob.exists()
        else:
            return os.path.exists(path)

    def read_csv(self, path):
        if self.use_gcs:
            blob = self.bucket.blob(path)
            content = blob.download_as_string()
            return pd.read_csv(BytesIO(content))
        else:
            return pd.read_csv(path)

    def write_csv(self, df, path):
        if self.use_gcs:
            blob = self.bucket.blob(path)
            blob.upload_from_string(df.to_csv(index=False), content_type='text/csv')
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            df.to_csv(path, index=False)

    def read_text(self, path):
        if self.use_gcs:
            blob = self.bucket.blob(path)
            return blob.download_as_text()
        else:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

    def write_text(self, content, path):
        if self.use_gcs:
            blob = self.bucket.blob(path)
            blob.upload_from_string(content)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

    def list_files(self, prefix):
        if self.use_gcs:
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        else:
            files = []
            for root, _, filenames in os.walk(prefix):
                for filename in filenames:
                    files.append(os.path.join(root, filename))
            return files

storage = StorageManager()
