"""Custom CloudFormation Resource to describe details of an existing SMStudio domain

You might want to do this if you:
- Know a SageMaker Studio domain is present but don't know its ID
- Need to know some other attribute not listed in AWS::SageMaker::Domain outputs

https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-sagemaker-domain.html

This resource will fail if no SMStudio domain is present in the region, or a DomainID is passed which does
not exist.
"""

# Python Built-Ins:
import logging
import traceback

# External Dependencies:
import boto3
import cfnresponse

smclient = boto3.client("sagemaker")

# The set of DescribeDomain response props that will be passed through to cfn output:
SUPPORTED_PROPS = {
    "DomainArn",
    "DomainId",
    "DomainName",
    "HomeEfsFileSystemId",
    "SingleSignOnManagedApplicationInstanceId",
    "Status",
    "AuthMode",
    "DefaultUserSettings",
    "AppNetworkAccessType",
    "HomeEfsFileSystemKmsKeyId",
    "SubnetIds",
    "Url",
    "VpcId",
    "KmsKeyId",
}

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


class NoStudioDomains(RuntimeError):
    pass


def infer_domain_id():
    domains_resp = smclient.list_domains()
    if "NextToken" in domains_resp:
        logging.warning(
            f"Ignoring NextToken on sagemaker:ListDomains response - pagination not implemented"
        )
    domain_ids = [d["DomainId"] for d in domains_resp["Domains"]]

    if not (len(domain_ids) > 0):
        # If the domain has been deleted, the user must necessarily have been deleted too!
        raise NoStudioDomains(f"No SageMaker Studio domain exists in this region!")
    elif len(domain_ids) > 1:
        logging.warning(
            f"Found {len(domain_ids)} Studio domains in this region: assuming first is target. {domain_ids}"
        )
    return domain_ids[0]


def handle_create(event, context):
    logging.info("**Received create request")
    domain_id = event["ResourceProperties"].get("DomainId")
    if domain_id is None:
        logging.info("Inferring domain ID")
        domain_id = infer_domain_id()

    logging.info(f"Querying domain {domain_id}")
    desc = smclient.describe_domain(DomainId=domain_id)
    result = { k: desc[k] for k in desc.keys() if k in SUPPORTED_PROPS }
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        result,
        physicalResourceId=domain_id,
    )


def handle_delete(event, context):
    logging.info("**Received delete event")
    logging.info("Descriptive resource - nothing to delete")
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        {},
        physicalResourceId=event["PhysicalResourceId"],
    )


def handle_update(event, context):
    """Literally same process as create, for now - so as to always re-describe in case of changes
    """
    logging.info("**Received update event")
    domain_id = event["ResourceProperties"].get("DomainId")
    if domain_id is None:
        logging.info("Inferring domain ID")
        domain_id = infer_domain_id()

    logging.info(f"Querying domain {domain_id}")
    desc = smclient.describe_domain(DomainId=domain_id)
    result = { k: desc[k] for k in desc.keys() if k in SUPPORTED_PROPS }
    cfnresponse.send(
        event,
        context,
        cfnresponse.SUCCESS,
        result,
        physicalResourceId=domain_id,
    )
