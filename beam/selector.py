from typing import Optional

import aws_sso_lib
import questionary
import validators
import yaml
from questionary import Choice
from rich import print  # pylint: disable=redefined-builtin
from rich.panel import Panel

from beam.aws.utils import AwsOrganization
from beam.config_loader import BeamConfig, BeamAwsConfig, BeamBastionConfig, BeamKubernetesConfig, BeamEksConfig, BeamRdsConfig

AWS_REGIONS = [
    'us-east-1',
    'us-east-2',
    'us-west-1',
    'us-west-2',
    'ap-south-1',
    'ap-south-2',
    'ap-northeast-3',
    'ap-northeast-2',
    'ap-southeast-1',
    'ap-southeast-2',
    'ap-southeast-3',
    'ap-southeast-4',
    'ap-northeast-1',
    'ap-east-1',
    'ca-central-1',
    'eu-central-1',
    'eu-central-2',
    'eu-west-1',
    'eu-west-2',
    'eu-west-3',
    'eu-south-1',
    'eu-south-2',
    'eu-north-1',
    'sa-east-1',
    'me-central-1',
    'il-central-1',
    'af-south-1',
    'me-south-1',
]


def get_available_aws_regions(organization: AwsOrganization, role_name: str) -> list[str]:
    available_regions = organization.get_all_regions(role_name)
    return sorted(available_regions) or AWS_REGIONS


def _validate_aws_sso_url(url: str) -> bool | str:
    if not validators.url(url):
        return 'Invalid URL'

    return True


def ask_for_config(config_path: str, sso_url: str, sso_region: str) -> Optional[BeamConfig]:
    """
    :param config_path:
    :param sso_url:
    :param sso_region:
    :return: BeamConfig
    """

    if not (sso_url and sso_region):
        sso_url = questionary.text('What is your SSO URL?', validate=_validate_aws_sso_url).unsafe_ask()
        sso_region = questionary.select('What is your SSO region?', choices=AWS_REGIONS).unsafe_ask()

    aws_sso_lib.login(sso_url, sso_region)

    organization = AwsOrganization(sso_url, sso_region)
    available_aws_accounts = organization.get_accounts()

    aws_accounts = questionary.checkbox('What are your AWS accounts?',
                                        choices=[Choice(title=account.name, value=str(account.id)) for account in available_aws_accounts],
                                        validate=lambda x: True if bool(x) else 'Please select at least one account',
                                        ).unsafe_ask()

    all_available_aws_roles = {role[2] for account in available_aws_accounts for role in organization.get_all_roles(account)}
    print(
        'Please choose your preferred Permission Set. '
        '[bold bright_yellow]Notice that this Permission Set will be used to connect to all your accounts.[/bold bright_yellow]')
    aws_role = questionary.select('Permission Set',
                                  choices=all_available_aws_roles,
                                  ).unsafe_ask()

    aws_regions = questionary.checkbox('Please choose your regions',
                                       # choices=get_available_aws_regions(organization, aws_role),
                                       choices=AWS_REGIONS,
                                       validate=lambda x: True if bool(x) else 'Please select at least one region',
                                       ).unsafe_ask()

    aws = BeamAwsConfig(sso_url, sso_region, aws_role, aws_accounts, aws_regions)

    bastion_regex = questionary.text('What is the regex to detect your bastion?', '*bastion*').unsafe_ask()
    tags = dict(Name=bastion_regex) if bastion_regex else {}
    bastion = BeamBastionConfig(tags=tags)

    kubernetes_namespace = questionary.text('What is your preferred kubernetes namespace?', default='default').unsafe_ask()
    kubernetes = BeamKubernetesConfig(namespace=kubernetes_namespace)

    eks_enabled = questionary.confirm('Do you want to enable EKS?').unsafe_ask()
    eks = BeamEksConfig(enabled=eks_enabled)
    if eks_enabled:
        eks_regex = questionary.text('What is the regex to detect your EKS cluster? Leave empty to detect all').unsafe_ask()
        eks.tags = {'Name': eks_regex} if eks_regex else {}

    rds_enabled = questionary.confirm('Do you want to enable RDS?').unsafe_ask()
    rds = BeamRdsConfig(enabled=rds_enabled)
    if rds_enabled:
        rds_regex = questionary.text('What is the regex to detect your RDS instances? Leave empty to detect all').unsafe_ask()
        rds.tags = {'Name': rds_regex} if rds_regex else {}

    beam_config = BeamConfig(aws=aws,
                             bastion=bastion,
                             kubernetes=kubernetes,
                             eks=eks,
                             rds=rds,
                             )

    yaml_config = yaml.dump(beam_config.to_dict(), default_flow_style=False)

    yaml_config = '\n'.join(['    ' + line for line in yaml_config.split('\n')])  # add \t before each line

    print('\n')
    print('\t[red]Please approve the following config:[/red]\n')
    print(Panel.fit(f'{yaml_config}', title=config_path, border_style='red'))
    print('[bold red]This will override your current config![/bold red]\n')

    approve = questionary.confirm('Approve?',
                                  auto_enter=False,
                                  default=False,
                                  style=questionary.Style([
                                      ('question', 'fg:#cc5454 bold'),
                                  ])
                                  ).unsafe_ask()
    if not approve:
        print('Doing nothing')
        return None

    return beam_config
