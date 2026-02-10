#!/usr/bin/env python3
import os
import boto3
import logging
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# S3 bucket and prefix
# The bucket name which is created by CDK, you can see it in the output of CDK.
BUCKET_NAME = 'insights-jiatin-sourcebucketddd2130a-nmdfkizqni0h'
S3_PREFIX = 'test-data/'


def upload_file(file_path, bucket, object_name):
    """Upload a file to an S3 bucket

    :param file_path: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name
    :return: True if file was uploaded, else False
    """
    s3_client = boto3.client('s3')
    try:
        logger.info(f"Uploading {file_path} to s3://{bucket}/{object_name}")
        s3_client.upload_file(file_path, bucket, object_name)
        return True
    except ClientError as e:
        logger.error(f"Error uploading {file_path}: {e}")
        return False


def main():
    # Get all directories in the current folder
    current_dir = os.getcwd()
    dirs = [d for d in os.listdir(current_dir) if os.path.isdir(os.path.join(current_dir, d)) and not d.startswith('.')]

    # Store paths to metadata.json files to upload later
    metadata_files = []

    # First, upload all non-metadata.json files
    for dir_name in dirs:
        dir_path = os.path.join(current_dir, dir_name)
        logger.info(f"Processing directory: {dir_name}")

        for root, _, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)

                # Calculate the relative path from the current directory
                rel_path = os.path.relpath(file_path, current_dir)
                s3_key = os.path.join(S3_PREFIX, rel_path)

                # If it's metadata.json, store for later upload
                if file.lower() == 'metadata.json' in file_path:
                    metadata_files.append((file_path, s3_key))
                else:
                    upload_file(file_path, BUCKET_NAME, s3_key)

    # Now upload all metadata.json files
    logger.info("Uploading metadata.json files...")
    for file_path, s3_key in metadata_files:
        upload_file(file_path, BUCKET_NAME, s3_key)

    logger.info("Upload completed successfully!")


if __name__ == "__main__":
    main()