import os

import boto3
import pytest
from moto import mock_aws

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")

from navigator.store.data_store import DataStore  # noqa: E402
from navigator.store.schema import DATA_TABLE_DEF, USAGE_TABLE_DEF  # noqa: E402


@pytest.fixture
def aws():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-2")
        ddb.create_table(TableName="data-t", **DATA_TABLE_DEF)
        ddb.create_table(TableName="usage-t", **USAGE_TABLE_DEF)
        yield ddb


@pytest.fixture
def store(aws):
    return DataStore("data-t", resource=aws)
