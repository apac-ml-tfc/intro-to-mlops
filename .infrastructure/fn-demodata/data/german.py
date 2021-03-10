"""Demo data loader for UCI German Credit dataset

See https://archive.ics.uci.edu/ml/datasets/statlog+(german+credit+data)
"""

# Python Built-Ins:
import logging
import os
import traceback

# External Dependencies:
import boto3
import pandas as pd
import requests
import s3fs

logger = logging.getLogger("german")

GERMAN_SCHEMA = [
    {
        "name": "checking_acct_status",
        # A13 also means salary assignments for at least 1 year?
        "map": {
            "A11": "Band 1 <0DM",
            "A12": "Band 2 0-200DM",
            "A13": "Band 3 >=200DM",
            # Don't use 'N/A' or other strings Pandas interprets as null, if you don't want confusing
            # differences between how Pandas and PySpark processes interpret the data!
            # https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_csv.html#pandas.read_csv
            "A14": "No Account",
        },
    },
    {
        "name": "duration_months",
    },
    {
        "name": "credit_history",
        "map": {
            "A30": 0, #"A30 None taken or all paid duly",
            "A31": 1, #"A31 All credits at this bank paid back duly",
            "A32": 2, #"A32 Existing credits paid back duly til now",
            "A33": 3, #"A33 Delay in paying off in the past",
            "A34": 4, #"A34 Critical account",  # critical account/ other credits existing (not at this bank)
        },
    },
    {
        "name": "purpose",
        "map": {
            "A40": "car_new",
            "A41": "car_used",
            "A42": "furniture_equipment",
            "A43": "radio_television",
            "A44": "domestic_appliances",
            "A45": "repairs",
            "A46": "education",
            "A47": "vacation",  # Not actually present in data
            "A48": "retraining",
            "A49": "business",
            "A410": "others",
        },
    },
    {
        "name": "credit_amount",
    },
    {
        "name": "savings_status",
        "map": {
            "A61": "Band 1 <100DM",
            "A62": "Band 2 100-500DM",
            "A63": "Band 3 500-1000DM",
            "A64": "Band 4 >=1000DM",
            "A65": "Unknown or N/A",
        },
    },
    {
        "name": "present_employment_yrs_lt",
        "map": {
            "A71": 0,  # Unemployed
            "A72": 1,  # Under a year
            "A73": 4,  # 1-4yrs
            "A74": 7,  # 4-7yrs
            "A75": 10,  # >=7 years, value chosen to make it a passably regular ordinal encoding
        },
    },
    {
        "name": "installment_rate_disp_income_pct",
    },
    {
        "name": "marital_status_and_gender",
        "map": {
            "A91": "male : divorced/separated",
            "A92": "female : divorced/separated/married",
            "A93": "male : single",
            "A94": "male : married/widowed",
            "A95": "female : single",
        },
    },
    {
        "name": "other_parties",
        "map": {
            "A101": "none",
            "A102": "coapplicant",
            "A103": "guarantor",
        },
    },
    {
        "name": "present_residence_since",
    },
    {
        "name": "highest_property",
        "map": {
            "A121": "1 real estate",
            "A122": "2 savings agreement / life insurance",
            "A123": "3 car or other",
            "A124": "4 unknown or none"
        },
    },
    {
        "name": "age_in_years",
    },
    {
        "name": "other_installment_plans",
        "map": {
            "A141": "bank",
            "A142": "stores",
            "A143": "none",
        },
    },
    {
        "name": "housing",
        "map": {
            "A151": "rent",
            "A152": "own",
            "A153": "for_free",
        },
    },
    {
        "name": "n_existing_credits_this_bank",
    },
    {
        "name": "job_type",
        "map": {
            "A171": 0, # "unemployed/unskilled - non-resident",
            "A172": 1, # "unskilled - resident",
            "A173": 2, # "skilled/official",
            "A174": 3, # "management/self-employed/highly-qualified",
        },
    },
    {
        "name": "n_dependants",
    },
    {
        "name": "telephone",
        "map": {
            "A191": "none",
            "A192": "yes",
        },
    },
    {
        "name": "foreign_worker",
        "map": {
            "A201": "yes",
            "A202": "no",
        },
    },
    {
        "name": "credit_risk",
        "map": {
            1: "good",
            2: "bad",
        }
    }
]


def load(s3_bucket_name: str, s3_prefix: str, schema=GERMAN_SCHEMA):
    print(f"boto3 version: {boto3.__version__}")
    print(f"pandas version: {pd.__version__}")
    print(f"s3fs version: {s3fs.__version__}")
    logger.info("Fetching data...")
    res = requests.get(
        "http://archive.ics.uci.edu/ml/machine-learning-databases/statlog/german/german.data",
        stream=True,
    )

    logger.info("Extracting CSV...")
    colnames = [c["name"] for c in schema]
    with res.raw as rawdata:
        df = pd.read_csv(rawdata, sep=" ", names=colnames)

    assert len(colnames) == len(df.columns), "Downloaded data file did not match expected schema!"
    # Adjust for our use case:
    for colspec in schema:
        colname = colspec["name"]
        colmap = colspec.get("map")
        if colmap:
            df[colname] = df[colname].apply(lambda v: colmap.get(v, v))

    out_uri = f"s3://{s3_bucket_name}/{s3_prefix}german.csv"
    logger.info(f"Writing CSV to {out_uri}")
    print(f"Saving to {out_uri}")
    try:
        df.to_csv(out_uri, index=False)
    except Exception as e:
        # TODO: Why does pandas S3 auth not work correctly even with pinned versions? PermissionsError
        print(f"Preferred upload method failed - trying alternative")
        traceback.print_exc()
        bucketfs = s3fs.S3FileSystem(anon=False)  # uses default credentials
        with bucketfs.open(f"{s3_bucket_name}/{s3_prefix}german.csv", "wb") as f:
            df.to_csv(f, index=False)
