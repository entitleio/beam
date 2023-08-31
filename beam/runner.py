import concurrent
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

import yaml
from rich import print  # pylint: disable=redefined-builtin

from beam.aws.bastion import AwsBastion
from beam.aws.utils import AwsOrganization
from beam.config_loader import BeamConfig
from beam.utils import logger


class BeamRunner:
    def __init__(self, beam_config: BeamConfig, beam_config_path: str, organization: AwsOrganization, permission_set: str) -> None:
        self.beam_config = beam_config
        self.beam_config_path = beam_config_path
        self.aws_organization = organization
        self.permission_set = permission_set

    def scan_resources(self) -> list[AwsBastion]:
        bastions: list[AwsBastion] = []

        for account in self.aws_organization.get_accounts():
            if account.id not in self.beam_config.aws.accounts:
                logger.debug(f'Skipping account {account} as it is not in config')
                continue
            roles = {role[2] for role in self.aws_organization.get_all_roles(account)}
            if self.beam_config.aws.role not in roles:
                logger.debug(f'Skipping account {account} as role {self.beam_config.aws.role} is not in {roles}')
                continue
            logger.info(f'Found {len(roles)} roles: {roles}')
            logger.info(f'Processing account {account}')

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(self.aws_organization.process_account, account, self.permission_set, self.beam_config)
                ]
                for future in concurrent.futures.as_completed(futures):
                    if res := future.result():
                        logger.info(f'Found {len(res)} bastions: {res}')
                        bastions.extend(res)

        logger.info(f'Found {len(bastions)} bastions: {bastions}')

        # save bastions to local config to cache the scan
        self.beam_config.bastions = bastions
        beam_config_dict = self.beam_config.to_dict()
        os.makedirs(os.path.dirname(self.beam_config_path), exist_ok=True)
        with open(self.beam_config_path, 'w') as file:
            yaml.safe_dump(beam_config_dict, file, default_flow_style=False)

        return bastions

    def connect_to_resources(self, bastions: list[AwsBastion], is_eks_enabled: bool, is_rds_enabled: bool) -> list[subprocess.Popen]:
        processes: list[subprocess.Popen] = []

        for bastion in bastions:
            try:
                logger.debug(f'Connecting to Bastion {bastion}')

                if is_eks_enabled:
                    for eks_instance in bastion.eks_instances:
                        logger.debug(f'Processing EKS {eks_instance}')
                        if process := bastion.connect_to_eks(eks_instance, default_namespace=self.beam_config.kubernetes.namespace or 'default'):
                            processes.append(process)

                if is_rds_enabled:
                    for rds_instance in bastion.rds_instances:
                        logger.debug(f'Processing RDS {rds_instance}')
                        if process := bastion.connect_to_rds(rds_instance):
                            processes.append(process)
            except PermissionError as e:
                print(f'[bold red]ERROR: {e}[/bold red]')

        return processes
