"""Helper utilities for running SageMaker Data Wrangler flows"""

# Python Built-Ins:
import json
import os

# External Dependencies:
import boto3
from sagemaker.processing import ProcessingInput, ProcessingOutput, FeatureStoreOutput
from sagemaker.dataset_definition.inputs import AthenaDatasetDefinition, DatasetDefinition, RedshiftDatasetDefinition

def create_flow_notebook_processing_input(base_dir, flow_s3_uri):
    """Create the flow file processing input for a DW job

    (From Data Wrangler Job notebook template 2021-03-10)
    """
    return ProcessingInput(
        source=flow_s3_uri,
        destination=f"{base_dir}/flow",
        input_name="flow",
        s3_data_type="S3Prefix",
        s3_input_mode="File",
        s3_data_distribution_type="FullyReplicated",
    )


def create_s3_processing_input(s3_dataset_definition, name, base_dir):
    """Create an S3 processing input for a DW job

    (From Data Wrangler Job notebook template 2021-03-10)
    """
    return ProcessingInput(
        source=s3_dataset_definition['s3ExecutionContext']['s3Uri'],
        destination=f"{base_dir}/{name}",
        input_name=name,
        s3_data_type="S3Prefix",
        s3_input_mode="File",
        s3_data_distribution_type="FullyReplicated",
    )


def create_athena_processing_input(athena_dataset_defintion, name, base_dir):
    """Create an Athena processing input for a DW job

    (From Data Wrangler Job notebook template 2021-03-10)
    """
    return ProcessingInput(
        input_name=name,
        dataset_definition=DatasetDefinition(
            local_path=f"{base_dir}/{name}",
            data_distribution_type="FullyReplicated",
            athena_dataset_definition=AthenaDatasetDefinition(
                catalog=athena_dataset_defintion["catalogName"],
                database=athena_dataset_defintion["databaseName"],
                query_string=athena_dataset_defintion["queryString"],
                output_s3_uri=athena_dataset_defintion["s3OutputLocation"] + f"{name}/",
                output_format=athena_dataset_defintion["outputFormat"].upper()
            )
        )
    )


def create_redshift_processing_input(redshift_dataset_defintion, name, base_dir):
    """Create a Redshift processing input for a DW job

    (From Data Wrangler Job notebook template 2021-03-10)
    """
    return ProcessingInput(
        input_name=name,
        dataset_definition=DatasetDefinition(
            local_path=f"{base_dir}/{name}",
            data_distribution_type="FullyReplicated",
            redshift_dataset_definition=RedshiftDatasetDefinition(
                cluster_id=redshift_dataset_defintion["clusterIdentifier"],
                database=redshift_dataset_defintion["database"],
                db_user=redshift_dataset_defintion["dbUser"],
                query_string=redshift_dataset_defintion["queryString"],
                cluster_role_arn=redshift_dataset_defintion["unloadIamRole"],
                output_s3_uri=redshift_dataset_defintion["s3OutputLocation"] + f"{name}/",
                output_format=redshift_dataset_defintion["outputFormat"].upper()
            )
        )
    )


def create_processing_inputs(flow_local, flow_s3uri, processing_dir="/opt/ml/processing"):
    """Helper function for creating processing inputs
    :param flow_local: Local data wrangler flow file path
    :param flow_s3uri: S3 URI of the uploaded data wrangler flow file

    Modified from Data Wrangler Job notebook template 2021-03-10 to:
    - make processing_dir optional
    - Handle the upload & loading of the flow file
    """
    # Load the flow file JSON (good first validation step):
    with open(flow_local) as f:
        flow = json.load(f)
    # Push the flow file to S3:
    if not flow_s3uri.lower().startswith("s3://"):
        raise ValueError(f"flow_s3uri must be an S3 URI in the form s3://bucket/path... Got {flow_s3uri}")
    bucket, _, key = flow_s3uri[len("s3://"):].partition("/")
    boto3.client("s3").upload_file(flow_local, bucket, key)
    print(f"Uploaded {flow_local} to {flow_s3uri}")

    processing_inputs = []
    flow_processing_input = create_flow_notebook_processing_input(processing_dir, flow_s3uri)
    processing_inputs.append(flow_processing_input)

    for node in flow["nodes"]:
        if "dataset_definition" in node["parameters"]:
            data_def = node["parameters"]["dataset_definition"]
            name = data_def["name"]
            source_type = data_def["datasetSourceType"]

            if source_type == "S3":
                processing_inputs.append(create_s3_processing_input(data_def, name, processing_dir))
            elif source_type == "Athena":
                processing_inputs.append(create_athena_processing_input(data_def, name, processing_dir))
            elif source_type == "Redshift":
                processing_inputs.append(create_redshift_processing_input(data_def, name, processing_dir))
            else:
                raise ValueError(f"{source_type} is not supported for Data Wrangler Processing.")

    return processing_inputs


def create_featurestore_output(output_name, feature_group_name):
    """Create processing output for a Data Wrangler job to output to SageMaker Feature Store

    (Modified from Data Wrangler FS notebook template 2021-03-10 to use SageMaker SDK)
    """
    # SDK should be approx equivalent to:
    # {
    #   'Outputs': [
    #     {
    #       'OutputName': '42eac0fe-e5da-467f-adfd-bb4c4fae57cb.default',
    #       'FeatureStoreOutput': {
    #         'FeatureGroupName': feature_group_name
    #       },
    #       'AppManaged': True
    #     }
    #   ],
    # }
    return ProcessingJobOutput(
        output_name=output_name,
        app_managed=True,
        feature_store_output=FeatureStoreOutput(feature_group_name="hi"),
    )


def create_s3_output(output_name, output_s3uri, processing_dir="/opt/ml/processing"):
    """Create ProcessingOutput for a Data Wrangler job to output to S3

    (From Data Wrangler Job notebook template 2021-03-10)
    """
    return ProcessingOutput(
        output_name=output_name,
        source=os.path.join(processing_dir, "output"),
        destination=output_s3uri,
        s3_upload_mode="EndOfJob",
    )


def create_container_arguments(output_name: str, output_content_type: str="CSV"):
    """Create Data Wrangler processing job CLI arguments

    :param output_name: Name of the flow node to be output
    :param output_content_type: set "CSV" (default) or "PARQUET"

    (From Data Wrangler Job notebook template 2021-03-10)
    """
    output_config = {
        output_name: {
            "content_type": output_content_type
        }
    }
    return [f"--output-config '{json.dumps(output_config)}'"]
