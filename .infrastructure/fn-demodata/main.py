"""Custom CloudFormation Resource to download demo data for a workshop
"""

# Python Built-Ins:
import json
import logging
import os
import time
import traceback

# External Dependencies:
import boto3
from botocore.exceptions import ClientError
import cfnresponse

# Local Dependencies:
import data

logger = logging.getLogger("main")

def lambda_handler(event, context):
    try:
        request_type = event["RequestType"]
        if request_type == "Create":
            handle_create(event, context)
        elif request_type == "Update":
            handle_update(event, context)
        elif request_type == "Delete":
            handle_delete(event, context)
        else:
            cfnresponse.send(
                event,
                context,
                cfnresponse.FAILED,
                {},
                error=f"Unsupported CFN RequestType '{request_type}'",
            )
    except Exception as e:
        logging.error("Uncaught exception in CFN custom resource handler - reporting failure")
        traceback.print_exc()
        cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            error=str(e),
        )
        raise e


def handle_create(event, context):
    logging.info("**Received create request")
    resource_config = event["ResourceProperties"]
    try:
        dataset_name = resource_config["Dataset"]
        s3_bucket_name = resource_config["Bucket"]
        s3_prefix = resource_config["Prefix"]
    except KeyError as ke:
        missing_param_name = ke.args[0]
        errmsg = f"Request missing required ResourceProperties parameter {missing_param_name}"
        logger.error(errmsg)
        return cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            error=errmsg,
        )

    logger.info("**Setting up demo data")
    data.load(dataset_name, s3_bucket_name, s3_prefix)

    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {},
        physicalResourceId=f"s3://{s3_bucket_name}/{s3_prefix}",
    )


def handle_delete(event, context):
    logging.info("**Received delete event")
    s3_uri = event["PhysicalResourceId"]
    if s3_uri.startswith("s3://"):
        s3_bucket_name, _, s3_prefix = s3_uri[len("s3://"):].partition("/")
        logger.info("**Deleting demo data")
        data.delete(s3_bucket_name, s3_prefix)
    else:
        logger.info("**Skipping - no S3 URI physical resource created")

    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {},
        physicalResourceId=event["PhysicalResourceId"],
    )


def handle_update(event, context):
    logging.info("**Received update event")
    logger.warning("**Update not yet implemented!")
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {},
        physicalResourceId=event["PhysicalResourceId"],
    )
