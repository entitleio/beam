import concurrent
import fnmatch
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import aws_sso_lib
import boto3

from beam.aws.bastion import AwsBastion
from beam.aws.models import AwsEksInstance, Boto3SessionConfig, AwsAccount, AwsRdsInstance
from beam.config_loader import BeamConfig
from beam.utils import add_profile_to_aws_config, logger


class AwsOrganization:
    def __init__(self, sso_start_url: str, sso_region: str) -> None:
        self.sso_start_url = sso_start_url
        self.sso_region = sso_region
        self.accounts: list[tuple[str, str]] = []

    def get_accounts(self) -> list[AwsAccount]:
        self.accounts = list(aws_sso_lib.list_available_accounts(self.sso_start_url, self.sso_region))
        logger.debug(f'Found {len(self.accounts)} accounts: {self.accounts}')
        return [AwsAccount(account[0], account[1]) for account in self.accounts]

    def get_all_roles(self, account: AwsAccount) -> list[tuple[str, str, str]]:
        account_id = account.id
        roles = list(aws_sso_lib.list_available_roles(self.sso_start_url, self.sso_region, account_id))
        logger.debug(f'Found {len(roles)} roles in account {account_id}: {roles}')
        return roles

    def get_session(self, account_id: str, permission_set_name: str, region: str) -> boto3.Session:
        return aws_sso_lib.get_boto3_session(self.sso_start_url, account_id=account_id,
                                             role_name=permission_set_name,
                                             sso_region=self.sso_region, region=region)

    def process_account(self, account: AwsAccount, role: str, beam_config: BeamConfig) -> list[AwsBastion]:
        logger.info(f'Processing account {account.id}')
        account_id = account.id
        session = aws_sso_lib.get_boto3_session(self.sso_start_url, account_id=account_id,
                                                role_name=role,
                                                sso_region=self.sso_region, region=self.sso_region)
        add_profile_to_aws_config(account_id, role, self.sso_start_url, session.region_name, session.region_name, False)

        bastions = []

        for region in beam_config.aws.regions:
            session_config = Boto3SessionConfig(account_id, self.sso_start_url, self.sso_region, role, region)

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(process_region, session_config, region, beam_config)]
                for future in concurrent.futures.as_completed(futures):
                    if future.result():
                        bastions.extend(future.result())

        return bastions

    def get_all_regions(self, permission_set_name: str) -> list[str]:
        regions: set[str] = set()
        for account in self.get_accounts():
            session = aws_sso_lib.get_boto3_session(self.sso_start_url, self.sso_region, account.id, permission_set_name, region=self.sso_region)
            ec2_client = session.client('ec2')
            logger.debug(f'Retrieving AWS regions for account {account.id}')

            try:
                response = ec2_client.describe_regions()
                regions.update({region['RegionName'] for region in response['Regions']})
            except Exception as e:
                logger.exception(f'An error occurred while retrieving AWS regions: {e}')

        return list(regions)


def get_all_eks_clusters(session: boto3.Session, tags: Optional[dict[str, str]] = None) -> List[AwsEksInstance]:
    """
    Retrieves a list of all EKS clusters in the account.
    :param session: boto3 session
    :param tags: tags to match, 'Name' can be used with wildcards
    :return: list of eks clusters
    """
    tags = tags or {}
    client = session.client('eks')
    paginator = client.get_paginator('list_clusters')
    response_iterator = paginator.paginate()
    cluster_names = []
    for response in response_iterator:
        cluster_names.extend(response['clusters'])

    eks_list = []

    for cluster_name in cluster_names:
        try:
            response = client.describe_cluster(name=cluster_name)
            cluster = response['cluster']

            if not match_tags(cluster['tags'], tags):
                continue

            eks_list.append(AwsEksInstance(cluster['name'], cluster['endpoint'], cluster['arn'], cluster['resourcesVpcConfig']['vpcId']))
        except (client.exceptions.ResourceNotFoundException, client.exceptions.InvalidParameterException):
            logger.exception(f'Error describing cluster {cluster_name}')
        except Exception as e:
            logger.exception(
                f'Error describing cluster {cluster_name}')  # decide whether to continue or stop execution based on the type of exception
            raise e

    return eks_list


def get_all_rds_resources(session: boto3.Session, tags: Optional[dict[str, str]] = None) -> list[AwsRdsInstance]:
    """
    Retrieves all RDS resources (instances and clusters)
    :param session: boto3 session
    :param tags: tags to match, 'Name' can be used with wildcards
    """
    tags = tags or {}
    client = session.client('rds')

    # Retrieve instances using paginator
    paginator = client.get_paginator('describe_db_instances')
    response_iterator = paginator.paginate()
    instances = [instance for response in response_iterator for instance in response['DBInstances']]

    # Retrieve clusters using paginator
    paginator = client.get_paginator('describe_db_clusters')
    response_iterator = paginator.paginate()
    clusters = [cluster for response in response_iterator for cluster in response['DBClusters']]

    # Filter resources based on status
    available_instances = [i for i in instances if i['DBInstanceStatus'] == 'available']
    available_clusters = [c for c in clusters if c['Status'] == 'available']

    # Create a list of dictionaries for instances and clusters
    instance_resources: list[AwsRdsInstance] = []

    name_regex = tags.pop('Name', None)

    for instance in available_instances:
        # apply user filtering
        if name_regex:
            if not fnmatch.fnmatch(instance['DBInstanceIdentifier'], name_regex):
                continue
        if not match_key_value_tags(instance['TagList'], tags):
            continue
        instance_resources.append(AwsRdsInstance(instance['DBInstanceIdentifier'],
                                                 instance['Endpoint']['Address'],
                                                 int(instance['Endpoint']['Port']), instance['DBSubnetGroup']['VpcId'])
                                  )
    cluster_resources = []
    for cluster in available_clusters:
        # apply user filtering
        if name_regex:
            if not fnmatch.fnmatch(cluster['DBClusterIdentifier'], name_regex):
                continue

        if not match_tags(cluster['TagList'], tags):
            continue

        cluster_resources.append(AwsRdsInstance(cluster['DBClusterIdentifier'],
                                                cluster['Endpoint'],
                                                int(cluster['Port']))
                                 )

    # Return the combined list of resources
    return instance_resources + cluster_resources


def get_matching_ec2_instance(session: boto3.Session, session_config: Boto3SessionConfig,
                              name_regex: Optional[str],
                              filter_tags: Optional[dict[str, str]] = None) -> list[AwsBastion]:
    """
    Retrieves a list of EC2 instances that match the given criteria.

    :param session: An instance of boto3.session.Session.
    :param session_config: An instance of Boto3SessionConfig.
    :param name_regex: A string representing the regular expression for matching instance names.
    :param filter_tags: A dictionary of tags to filter by.
    :returns: A list of bastion instances that match the given criteria.
    """
    # TODO: should support multi-bastion per-region (e.g. for multiple VPCs)
    filter_tags = filter_tags or {}

    bastions = []
    try:
        ec2_client = session.resource('ec2', region_name=session_config.region)
        filters = [{'Name': 'tag:' + tag_key, 'Values': [tag_value]} for tag_key, tag_value in filter_tags.items()]
        filters.append({'Name': 'instance-state-name', 'Values': ['running']})  # running instances only
        instances = list(ec2_client.instances.filter(Filters=filters))

        for instance in instances:
            logger.debug(f'Found EC2 instance: {instance.instance_id}')
            instance_tags = {tag['Key']: tag['Value'] for tag in instance.tags}
            instance_name = instance_tags.get('Name', '')

            if not fnmatch.fnmatchcase(instance_name, name_regex):
                continue

            logger.debug(f'EC2 instance matched: {instance_name}')

            bastions.append(
                AwsBastion(
                    boto3_session_config=session_config,
                    instance_id=instance.instance_id, name=instance_name, vpc_id=instance.vpc_id)
            )
    except Exception as e:
        logger.exception(f'Could not retrieve EC2 instances in region {session_config.region}: {e}')

    return bastions


def get_profile_name(account_id: str, permission_set_name: str) -> str:
    return f'{account_id}-{permission_set_name}'


def process_region(session_config: Boto3SessionConfig, region: str, beam_config: BeamConfig) -> list[AwsBastion]:
    logger.info(f'Processing account {session_config.account_id} in region {region}')
    boto3_session = session_config.get_session()

    ekss = get_all_eks_clusters(boto3_session, beam_config.eks.tags)
    rdss = get_all_rds_resources(boto3_session, beam_config.rds.tags)
    region_bastions = get_matching_ec2_instance(boto3_session, session_config, beam_config.bastion.name, beam_config.bastion.other_tags)

    if not region_bastions:
        return []

    for bastion in region_bastions:
        for eks in ekss:
            if eks.vpc_id == bastion.vpc_id:
                bastion.add_eks_instance(eks)

        for rds in rdss:
            if rds.vpc_id == bastion.vpc_id:
                bastion.add_rds_instance(rds)

    return region_bastions


def match_key_value_tags(actual_tags: list, desired_tags: dict) -> bool:
    for expected_tag_key, expected_tag_value in desired_tags.items():
        if not any(actual_tag['Key'] == expected_tag_key and actual_tag['Value'] == expected_tag_value for actual_tag in actual_tags):
            return False

    return True


def match_tags(actual_tags: dict[str, str], desired_tags: dict[str, str]) -> bool:
    if name_regex := desired_tags.get('Name'):
        if not fnmatch.fnmatchcase(actual_tags.get('Name', ''), name_regex):
            return False
        desired_tags.pop('Name')

    for expected_tag_key, expected_tag_value in desired_tags.items():
        if not actual_tags.get(expected_tag_key) == expected_tag_value:
            return False

    return True
