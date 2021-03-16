"""Custom CloudFormation Resource to attach a policy to execution roles by SageMaker Studio user names"""

# Python Built-Ins:
import json
import logging
import time
import traceback

# External Dependencies:
import boto3
from botocore.exceptions import ClientError
import cfnresponse

iamclient = boto3.client("iam")
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

    try:
        usernames = resource_config["Users"]
        policy_arn = resource_config["PolicyArn"]
    except KeyError as ke:
        missing_param_name = ke.args[0]
        errmsg = f"Request missing required ResourceProperties parameter {missing_param_name}"
        logging.error(errmsg)
        return cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            error=errmsg,
        )

    logging.info("**Creating policy attachments")
    result = create_attachments(usernames, policy_arn)
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        result,
        physicalResourceId=policy_arn,
    )


def handle_delete(event, context):
    logging.info("**Received delete event")
    physical_id = event["PhysicalResourceId"]
    resource_config = event["ResourceProperties"]

    try:
        usernames = resource_config["Users"]
        policy_arn = resource_config["PolicyArn"]
    except KeyError as ke:
        missing_param_name = ke.args[0]
        msg = f"Skipping policy detach as {missing_param_name} parameter missing"
        logging.warning(msg)
        return cfnresponse.send(
            event,
            context,
            cfnresponse.SUCCESS,
            {},
            physicalResourceId=physical_id,
        )

    logging.info("**Deleting policy attachments")
    result = delete_attachments(usernames, policy_arn)
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {},
        physicalResourceId=physical_id,
    )


def handle_update(event, context):
    logging.info("**Received update event")
    # old_physical_id = event["PhysicalResourceId"]
    new_config=event["ResourceProperties"]
    old_config=event["OldResourceProperties"]

    try:
        new_usernames = new_config["Users"]
        new_policy_arn = new_config["PolicyArn"]
    except KeyError as ke:
        missing_param_name = ke.args[0]
        errmsg = f"New ResourceProperties missing required parameter {missing_param_name}"
        logging.error(errmsg)
        return cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            error=errmsg,
        )

    old_policy_arn = old_config.get("PolicyArn")
    policy_changed = new_policy_arn != old_policy_arn
    old_usernames = old_config.get("Users", [])

    users_added = [u for u in new_usernames if u not in old_usernames]
    users_removed = [u for u in old_usernames if u not in new_usernames]

    any_changes = False
    # First, handle detachments:
    if old_policy_arn:
        if policy_changed:
            manage_attachments(old_usernames, old_policy_arn, attach=False)
            any_changes = True
        elif len(users_removed):
            manage_attachments(users_removed, old_policy_arn, attach=False)
            any_changes = True
    # Then, handle attachments:
    if policy_changed:
        manage_attachments(new_usernames, new_policy_arn, attach=True)
        any_changes = True
    elif len(users_added):
        manage_attachments(users_added, new_policy_arn, attach=True)
        any_changes = True

    if any_changes:
        time.sleep(20)  # Allow propagation time
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {
            "Users": new_usernames,
            "PolicyArn": new_policy_arn,
        },
        physicalResourceId=new_policy_arn,
    )


def manage_attachments(usernames, policy_arn, attach=True):
    msg_verb = "Attach" if attach else "Detach"
    print(f"{msg_verb}ing usernames: {usernames}")
    # List SageMaker Studio domains
    domains_resp = smclient.list_domains()
    if "NextToken" in domains_resp:
        logging.warning(f"Ignoring NextToken on SageMaker:ListDomains response - pagination not implemented")
    domain_ids = [d["DomainId"] for d in domains_resp["Domains"]]

    if (len(usernames) > 0) and not (len(domain_ids) > 0):
        raise ValueError("Found no SageMaker Studio domains in this region to search usernames on")

    # We'll track which roles we attach the policy to in case users share roles - no point duplicating:
    roles_processed = set()
    for username in usernames:
        try:
            user_role = None
            for domain_id in domain_ids:
                try:
                    user_desc = smclient.describe_user_profile(DomainId=domain_id, UserProfileName=username)
                except smclient.exceptions.ResourceNotFound:
                    continue  # User not found in this domain
                user_role = user_desc["UserSettings"]["ExecutionRole"]
                break
            if not user_role:
                raise ValueError(f"User not found in any SMStudio domains from {domain_ids}")

            if user_role in roles_processed:
                logging.info(f"Skipping user {username} as role {user_role} already processed")
                continue

            user_role_name = user_role.rpartition("/")[2]
            print(f"Extracted user_role_name {user_role_name} from {user_role}")
            if attach:
                iamclient.attach_role_policy(PolicyArn=policy_arn, RoleName=user_role_name)
            else:
                iamclient.detach_role_policy(PolicyArn=policy_arn, RoleName=user_role_name)
            roles_processed.add(user_role)
            time.sleep(0.1)

        except Exception as e:
            raise RuntimeError(f"Failed to {msg_verb.lower()} policies for user '{username}': {e}") from e

    return {
        "Users": usernames,
        "RoleArns": sorted(roles_processed),
    }


def create_attachments(usernames, policy_arn):
    result = manage_attachments(usernames, policy_arn, attach=True)
    time.sleep(20)  # Give attachments some time to propagate in case next resource requires them
    logging.info("**User profiles attached to policy successfully")
    return result


def delete_attachments(usernames, policy_arn):
    result = manage_attachments(usernames, policy_arn, attach=False)
    time.sleep(20)  # Give attachments some time to propagate in case next resource requires them
    logging.info("**User profiles detached from policy successfully")
    return result
