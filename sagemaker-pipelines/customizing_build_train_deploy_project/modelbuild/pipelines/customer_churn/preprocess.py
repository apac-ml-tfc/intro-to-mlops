# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
#     http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
"""Feature engineer and train/test split the customer churn dataset."""

import argparse
import logging
import pathlib

import boto3
import numpy as np
import pandas as pd
import os
import glob

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

if __name__ == "__main__":
    logger.info("Starting preprocessing.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-data", type=str, required=True)
    args = parser.parse_args()

    base_dir = "/opt/ml/processing"

    logger.info("Reading downloaded data from /opt/ml/processing/input/")
    
    if len(glob.glob(f"{base_dir}/input/*.csv"))>1:
        df = pd.concat(map(pd.read_csv, glob.glob(f"{base_dir}/input/*.csv")))
    else:
        df=pd.read_csv(glob.glob(f"{base_dir}/input/*.csv")[0])

    
    # Drop several columns
    df = df.drop(["txn_id", "txn_timestamp", "dataset"], axis=1)
    
    # Split the data
    train_data, validation_data, test_data = np.split(
        df.sample(frac=1, random_state=1729),
        [int(0.7 * len(df)), int(0.9 * len(df))],
    )

    pd.DataFrame(train_data).to_csv(
        f"{base_dir}/train/train.csv", header=False, index=False
    )
    pd.DataFrame(validation_data).to_csv(
        f"{base_dir}/validation/validation.csv", header=False, index=False
    )
    pd.DataFrame(test_data).to_csv(
        f"{base_dir}/test/test.csv", header=False, index=False
    )
