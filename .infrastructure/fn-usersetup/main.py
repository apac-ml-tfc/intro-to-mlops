"""Custom CloudFormation Resource for post-creation setup of a SageMaker Studio user

Clones a (public) 'GitRepository' into the user's home folder.

Updating or deleting this resource does not currently do anything. Errors in the setup process are also
ignored (typically don't want to roll back the whole stack just because we couldn't clone a repo - as users
can always do it manually!)
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
from git import Repo

smclient = boto3.client("sagemaker")
scclient = boto3.client("servicecatalog")

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
    logging.info("**Setting up user")
    result = create_user_setup(resource_config)
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
    enable_projects = event["ResourceProperties"].get("EnableProjects", False)
    logging.info("**Deleting user setup")
    delete_user_setup(domain_id, user_profile_name, enable_projects=enable_projects)
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
    git_repo = event["ResourceProperties"]["GitRepository"]
    logging.info("**Updating user setup")
    update_user_setup(domain_id, user_profile_name, git_repo)
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {},
        physicalResourceId=event["PhysicalResourceId"],
    )

def chown_recursive(path, uid=-1, gid=-1):
    """Workaround for os.chown() not having a recursive option for folders"""
    for dirpath, dirnames, filenames in os.walk(path):
        os.chown(dirpath, uid, gid)
        for filename in filenames:
            os.chown(os.path.join(dirpath, filename), uid, gid)

def enable_sm_projects_for_role(studio_role_arn):
    """Enable SageMaker Projects for a SageMaker Execution Role

    This function assumes you've already run Boto SageMaker enable_sagemaker_servicecatalog_portfolio() for
    the account as a whole
    """
    portfolios_resp = scclient.list_accepted_portfolio_shares()

    portfolio_ids = set()
    for portfolio in portfolios_resp["PortfolioDetails"]:
        if portfolio["ProviderName"] == "Amazon SageMaker":
            portfolio_ids.add(portfolio["Id"])

    logging.info(f"Adding {len(portfolio_ids)} SageMaker SC portfolios to role {studio_role_arn}")
    for portfolio_id in portfolio_ids:
        scclient.associate_principal_with_portfolio(
            PortfolioId=portfolio_id,
            PrincipalARN=studio_role_arn,
            PrincipalType="IAM"
        )


def disable_sm_projects_for_role(studio_role_arn):
    """Enable SageMaker Projects for a SageMaker Execution Role

    This function assumes you've already run Boto SageMaker enable_sagemaker_servicecatalog_portfolio() for
    the account as a whole
    """
    portfolios_resp = scclient.list_accepted_portfolio_shares()

    portfolio_ids = set()
    for portfolio in portfolios_resp["PortfolioDetails"]:
        if portfolio["ProviderName"] == "Amazon SageMaker":
            portfolio_ids.add(portfolio["Id"])

    logging.info(f"Removing {len(portfolio_ids)} SageMaker SC portfolios from role {studio_role_arn}")
    for portfolio_id in portfolio_ids:
        response = scclient.disassociate_principal_from_portfolio(
            PortfolioId=portfolio_id,
            PrincipalARN=studio_role_arn,
        )


def create_user_setup(config):
    domain_id = config["DomainId"]
    user_profile_name = config["UserProfileName"]
    git_repo = config["GitRepository"]
    efs_uid = config["HomeEfsFileSystemUid"]
    enable_projects = config.get("EnableProjects", False)

    print(f"Setting up user: {config}")
    ## First, Git clone repository in:
    try:
        # The root of the EFS contains folders named for each user UID, but these may not be created before
        # the user has first logged in (could os.listdir("/mnt/efs") to check):
        print("Creating/checking home folder...")
        home_folder = f"/mnt/efs/{efs_uid}"
        os.makedirs(home_folder, exist_ok=True)
        # Set correct ownership permissions for this folder straight away, in case a later process errors out
        os.chown(home_folder, int(efs_uid), -1)

        # Now ready to clone in Git content (or whatever else...)
        print(f"Cloning code... {git_repo}")
        # Our target folder for Repo.clone_from() needs to be the *actual* target folder, not the parent
        # under which a new folder will be created, so we'll infer that from the repo name:
        repo_folder_name = git_repo.rpartition("/")[2]
        if repo_folder_name.lower().endswith(".git"):
            repo_folder_name = repo_folder_name[:-len(".git")]
        Repo.clone_from(git_repo, f"{home_folder}/{repo_folder_name}")

        # Remember to set ownership/permissions for all the stuff we just created, to give the user write
        # access:
        chown_recursive(f"{home_folder}/{repo_folder_name}", uid=int(efs_uid))
        print("Home folder content setup complete")
    except Exception as e:
        # Don't bring the entire CF stack down just because we couldn't copy a repo:
        print("IGNORING CONTENT SETUP ERROR")
        traceback.print_exc()

    ## Finally enable SageMaker Projects/JumpStart if requested:
    if enable_projects:
        # We need to look up the role ARN for the user:
        user_desc = smclient.describe_user_profile(DomainId=domain_id, UserProfileName=user_profile_name)
        user_role_arn = user_desc["UserSettings"]["ExecutionRole"]
        enable_sm_projects_for_role(user_role_arn)

    logging.info("**SageMaker Studio user '%s' set up successfully", user_profile_name)
    return { "UserProfileName": user_profile_name }


def delete_user_setup(domain_id, user_profile_name, enable_projects=False):
    logging.info(
        "**Deleting user setup is a no-op: user '%s' on domain '%s",
        user_profile_name,
        domain_id,
    )

    ## Disable SageMaker Projects/JumpStart if requested:
    if enable_projects:
        # We need to look up the role ARN for the user:
        user_desc = smclient.describe_user_profile(DomainId=domain_id, UserProfileName=user_profile_name)
        user_role_arn = user_desc["UserSettings"]["ExecutionRole"]
        disable_sm_projects_for_role(user_role_arn)

    return { "UserProfileName": user_profile_name }


def update_user_setup(domain_id, user_profile_name, git_repo):
    logging.warning(
        "**Updating user setup is a no-op: user '%s' on domain '%s",
        user_profile_name,
        domain_id,
    )
    return { "UserProfileName": user_profile_name }
