# External Dependencies
import boto3

# Local Dependencies:
from . import german

def load(dataset_name, s3_bucket_name, s3_prefix):
    dsname_lower = dataset_name.lower()
    if s3_prefix.startswith("/"):
        s3_prefix = s3_prefix[1:]
    if len(s3_prefix) > 0 and not s3_prefix.endswith("/"):
        s3_prefix = s3_prefix + "/"
    if dsname_lower == "german":
        return german.load(s3_bucket_name, s3_prefix)
    else:
        raise ValueError(f"Unknown demo dataset name '{dataset_name}'")

def delete(s3_bucket_name, s3_prefix):
    if s3_prefix.startswith("/"):
        s3_prefix = s3_prefix[1:]
    bucket = boto3.resource("s3").Bucket(s3_bucket_name)
    for obj in bucket.objects.filter(Prefix=s3_prefix):
        # (obj is an s3.ObjectSummary)
        obj.delete()
