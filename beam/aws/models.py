from dataclasses import dataclass, field
from typing import Optional

import aws_sso_lib
import boto3
from dataclasses_json import DataClassJsonMixin, config

from beam.utils import hash_val


@dataclass
class Boto3SessionConfig(DataClassJsonMixin):
    account_id: str
    sso_start_url: str
    sso_region: str
    role_name: str
    region: str
    _session: Optional[boto3.Session] = field(init=False, default=None, metadata=config(exclude=lambda x: True,
                                                                                        encoder=lambda x: None,
                                                                                        decoder=lambda x: None))
    vpc_id: Optional[str] = None

    def get_session(self) -> boto3.Session:
        if self._session is None:
            self._session = aws_sso_lib.get_boto3_session(self.sso_start_url, account_id=self.account_id,
                                                          role_name=self.role_name,
                                                          sso_region=self.sso_region, region=self.region)
        return self._session


@dataclass
class AwsEksInstance:
    name: str
    endpoint: str
    arn: str
    vpc_id: Optional[str] = None


@dataclass
class AwsAccount:
    id: str
    name: str


@dataclass
class AwsRdsInstance:
    identifier: str
    endpoint: str
    port: int
    vpc_id: Optional[str] = None

    @property
    def local_port(self) -> int:
        return hash_val(self.endpoint) + 1024 * 16
