"""Utilities for reading & manipulating data in S3"""

# Python Built-Ins:
import re
from typing import List

# External Dependencies:
import boto3
import pandas as pd


def dataframe_from_s3_folder(s3uri: str, **kwargs):
    """Read (multiple) .csv files under an `s3uri` prefix into one combined Pandas DataFrame

    Implementation assumes your environment is set up for pd.read_csv("s3://...") to work (i.e. s3fs is
    installed with appropriate versions)

    :param s3uri: Source data prefix
    :param **kwargs: Passed through to Pandas.read_csv()
    """
    if not s3uri.lower().startswith("s3://"):
        raise ValueError(f"s3uri must be a valid S3 URI like s3://bucket/path... Got {s3uri}")
    bucket_name, _, prefix = s3uri[len("s3://"):].partition("/")
    bucket = boto3.resource("s3").Bucket(bucket_name)

    df = pd.DataFrame()
    for obj in bucket.objects.filter(Prefix=prefix):
        obj_key_lower = obj.key.lower()
        # Batch transform results come through with '.out', so we'll allow those too:
        if not (obj_key_lower.endswith(".csv") or obj_key_lower.endswith(".out")):
            continue
        print(f"Loading {obj.key}")
        obj_df = pd.read_csv(f"s3://{bucket_name}/{obj.key}", **kwargs)
        df = pd.concat((df, obj_df), axis=0, ignore_index=True)
    return df


def mock_featurestore_dataset_split(
    source_s3uri: str,
    out_s3uri: str,
    dataset_label_col: str="dataset",
    datasets_with_headers: str=r"train.*",
    drop_cols: List[str]=[],
):
    """Split a Data Wrangler output dataset by dataset segment (train/val/test)

    This process emulates splitting a source dataset (in S3) into segments (in S3) by a pre-prepared flag
    column... Analogous to how a real-world process might split a source dataset (in SM Feature Store) by
    queries (to S3)... For environments where Feature Store is not available.

    :param source_s3uri: Source dataset folder in S3
    :param out_s3uri: Root output folder in S3 (will create subfolders by dataset segment)
    :param dataset_label_col: Column label for the dataset flag (string e.g. train/val/test) field
    :param datasets_with_headers: RegEx identifying which segments will be output with column headers
    """
    # Load the full dataframe:
    df = dataframe_from_s3_folder(source_s3uri)
    # Drop FeatureStore fields not required for training, if present:
    df.drop(columns=["txn_id", "txn_timestamp"], errors="ignore")

    if out_s3uri.endswith("/"):
        out_s3uri = out_s3uri[:-1]

    datasets = df[dataset_label_col].unique()
    outputs = {}
    for dsname in datasets:
        outfile = f"{out_s3uri}/{dsname}/part0.csv"
        dsheaders = (
            re.match(datasets_with_headers, dsname) if isinstance(datasets_with_headers, str)
            else datasets_with_headersr
        )
        part_df = df[df[dataset_label_col] == dsname].drop(
            columns=[dataset_label_col] + drop_cols,
        )

        # Safety mechanism: Drop any string columns which will mess up the algorithm training job
        # (for demo, in case the user had to quit data prep early or made an error)
        str_cols = [
            col for col in part_df
            if (pd.api.types.is_string_dtype(part_df[col].dtype) and isinstance(part_df[col].iloc[0], str))
        ]
        if len(str_cols):
            print(f"WARNING: Text columns not supported by XGBoost - dropping {str_cols}")
            part_df = part_df.drop(columns=str_cols)

        # Fix for boolean fields `,true,` from DW getting converted to Python `,True,`
        for col in part_df:
            # pd.api.types.is_bool_dtype() doesn't seem to work in this situation for some reason - cols get
            # read in as object dtype with boolean values
            if isinstance(part_df[col].iloc[0], bool) and len(part_df[col].unique()) <= 2:
                part_df[col] = part_df[col].map(lambda x: "true" if x else "false")

        part_df.to_csv(
            outfile,
            index=False,
            header=dsheaders,
        )
        outputs[dsname] = [outfile]
    return outputs
