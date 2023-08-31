# pylint: disable=import-outside-toplevel
import subprocess
from dataclasses import dataclass, field
from typing import Optional

from dataclasses_json import DataClassJsonMixin

from beam.aws.models import Boto3SessionConfig, AwsRdsInstance, AwsEksInstance
from beam.eks import update_kubeconfig
from beam.hosts import edit_hosts_entry
from beam.ssm import start_ssm_forwarding_session
from beam.utils import hash_val, logger


@dataclass
class AwsBastion(DataClassJsonMixin):
    # session details
    boto3_session_config: Boto3SessionConfig

    # bastion details
    instance_id: str
    name: str
    vpc_id: str
    rds_instances: list[AwsRdsInstance] = field(default_factory=list, init=True)
    eks_instances: list[AwsEksInstance] = field(default_factory=list, init=True)

    def get_eks_clusters(self) -> list[AwsEksInstance]:
        from beam.aws.utils import get_all_eks_clusters  # local import is required to avoid circular imports
        eks_clusters = get_all_eks_clusters(self.boto3_session_config.get_session())
        logger.debug(f"Found {len(eks_clusters)} EKS clusters for bastion='{self.name}': {eks_clusters}")

        return eks_clusters

    def connect_to_eks(self, eks_instance: AwsEksInstance, default_namespace: str = 'default') -> Optional[subprocess.Popen]:
        from beam.aws.utils import get_profile_name  # local import is required to avoid circular imports

        session = self.boto3_session_config.get_session()
        account_id = self.boto3_session_config.account_id
        region = self.boto3_session_config.region
        bastion = self
        role = self.boto3_session_config.role_name

        logger.info(f'Connecting to EKS cluster {eks_instance.name}')
        cluster_endpoint_api = eks_instance.endpoint.replace('https://', '')
        edit_hosts_entry(cluster_endpoint_api)
        profile_name = get_profile_name(account_id, role)

        local_port = hash_val(eks_instance.endpoint) + (1024 * 16)

        update_kubeconfig(session, eks_instance.name, region, profile_name, local_port, default_namespace=default_namespace)
        process = start_ssm_forwarding_session(region, bastion.instance_id,
                                               cluster_endpoint_api, 443,
                                               local_port, profile_name)

        return process

    def connect_to_rds(self, rds_instance: AwsRdsInstance) -> Optional[subprocess.Popen]:
        from beam.aws.utils import get_profile_name  # local import is required to avoid circular imports
        session = self.boto3_session_config.get_session()
        edit_hosts_entry(rds_instance.endpoint)

        profile_name = get_profile_name(self.boto3_session_config.account_id, self.boto3_session_config.role_name)
        logger.info(f"Connecting to RDS instance '{rds_instance.identifier}' ({rds_instance.endpoint}:{rds_instance.local_port})")
        process = start_ssm_forwarding_session(session.region_name,
                                               self.instance_id,
                                               rds_instance.endpoint,
                                               rds_instance.port,
                                               rds_instance.local_port,
                                               profile_name)

        return process

    def add_rds_instance(self, rds_instance: AwsRdsInstance) -> None:
        self.rds_instances.append(rds_instance)

    def add_eks_instance(self, eks_instance: AwsEksInstance) -> None:
        self.eks_instances.append(eks_instance)

    def __str__(self) -> str:
        return f"{self.name} (id='{self.instance_id}', region='{self.boto3_session_config.region}', vpc='{self.vpc_id}')"

    def __repr__(self) -> str:
        return self.__str__()
