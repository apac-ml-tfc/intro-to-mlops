"""Custom CloudFormation Resource to initialize a SageMaker Studio user's default app

Speeds up workshop start time by eliminating initial JupyterServer app load
"""

# Python Built-Ins:
from datetime import datetime
import json
import logging
import os
import time
import traceback

# External Dependencies:
import boto3
from botocore.exceptions import ClientError
import cfnresponse

smclient = boto3.client("sagemaker")

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
    logging.info("**Setting up user's 'default' app")
    result = create_user_default_app(resource_config)
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        { "UserProfileName": result["UserProfileName"] },
        physicalResourceId=result["UserProfileName"],
    )


def handle_delete(event, context):
    logging.info("**Received delete event")
    user_profile_name = event["PhysicalResourceId"]
    domain_id = event["ResourceProperties"]["DomainId"]
    # logging.info("**Deleting user's 'default' app")
    # delete_user_setup(domain_id, user_profile_name)
    logging.info("**Ignoring event")
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {},
        physicalResourceId=event["PhysicalResourceId"],
    )


def handle_update(event, context):
    logging.info("**Received update event")
    user_profile_name = event["PhysicalResourceId"]
    domain_id = event["ResourceProperties"]["DomainId"]
    # logging.info("**Updating user setup")
    # update_user_setup(domain_id, user_profile_name, git_repo)
    logging.info("**Ignoring event")
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {},
        physicalResourceId=event["PhysicalResourceId"],
    )


def create_user_default_app(config):
    domain_id = config["DomainId"]
    user_profile_name = config["UserProfileName"]
    app_type = "JupyterServer"
    app_name = "default"
    print(f"Setting up user: {config}")
    created_arn = None
    try:
        create_app_response = smclient.create_app(
            DomainId=domain_id,
            UserProfileName=user_profile_name,
            AppType=app_type,
            AppName=app_name,
            ResourceSpec={ "InstanceType": "system",
            }
        )
        created_arn = create_app_response["AppArn"]
    except smclient.exceptions.ResourceLimitExceeded as elim:
        logging.info("CreateApp failed with ResourceLimitExceeded")
        traceback.print_exc()
    except smclient.exceptions.ResourceInUse as euse:
        logging.info("CreateApp failed with ResourceInUse")
        traceback.print_exc()
    except Exception as e:
        # Don't bring the entire CF stack down just because we couldn't copy a repo:
        print("IGNORING DEFAULT APP SETUP ERROR")
        traceback.print_exc()

    if created_arn is not None:
        status = None
        poll_secs = 30
        timeout_secs = 10 * 60
        t0 = datetime.now()
        while status not in ("Deleted", "Failed", "InService"):
            t = datetime.now()
            overall_secs = (t - t0).total_seconds()
            if overall_secs >= timeout_secs:
                logging.warning(f"**Wait timed out after {overall_secs}s")
                break
            try:
                app_desc = smclient.describe_app(
                    DomainId=domain_id,
                    UserProfileName=user_profile_name,
                    AppType=app_type,
                    AppName=app_name,
                )
                status = app_desc["Status"]
            except Exception as e:
                print("IGNORING DEFAULT APP STATUS POLLING ERROR")
                traceback.print_exc()
                break
            time.sleep(poll_secs)
        logging.info(f"Stopped wait with app in status {status}")

    logging.info("**SageMaker Studio user '%s' set up successfully", user_profile_name)
    return { "UserProfileName": user_profile_name }


def delete_user_default_app(domain_id, user_profile_name):
    logging.info(
        "**Deleting user setup is a no-op: user '%s' on domain '%s",
        user_profile_name,
        domain_id,
    )
    return { "UserProfileName": user_profile_name }


def update_user_default_app(domain_id, user_profile_name, git_repo):
    logging.info(
        "**Updating user setup is a no-op: user '%s' on domain '%s",
        user_profile_name,
        domain_id,
    )
    return { "UserProfileName": user_profile_name }
