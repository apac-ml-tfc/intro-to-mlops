"""Utilities for reading & manipulating data"""

# External Dependencies:
import boto3
import pandas as pd


def dataframe_from_s3_folder(s3uri):
    """Read (multiple) .csv files under an `s3uri` prefix into one combined Pandas DataFrame

    Implementation assumes your environment is set up for pd.read_csv("s3://...") to work (i.e. s3fs is
    installed with appropriate versions)
    """
    if not s3uri.lower().startswith("s3://"):
        raise ValueError(f"s3uri must be a valid S3 URI like s3://bucket/path... Got {s3uri}")
    bucket_name, _, prefix = s3uri[len("s3://"):].partition("/")
    bucket = boto3.resource("s3").Bucket(bucket_name)

    df = pd.DataFrame()
    for obj in bucket.objects.filter(Prefix=prefix):
        if not obj.key.lower().endswith(".csv"):
            continue
        print(f"Loading {obj.key}")
        obj_df = pd.read_csv(f"s3://{bucket_name}/{obj.key}")
        df = pd.concat((df, obj_df), axis=0, ignore_index=True)
    return df
