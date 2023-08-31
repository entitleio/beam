import configparser
import logging
import os
import platform
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional

import colorlog

logger = logging.getLogger('beam')
logger.setLevel(logging.DEBUG)

# DEFAULT_FORMAT = '%(asctime)s %(log_color)s[%(levelname)s]%(reset)s [%(name)s] %(module)s:\t%(log_color)s%(message)s%(reset)s'
DEFAULT_FORMAT = '%(log_color)s[%(levelname)s]%(reset)s [%(name)s] %(module)s: %(log_color)s%(message)s%(reset)s'

console_handler = colorlog.StreamHandler()
console_handler.setFormatter(colorlog.ColoredFormatter(DEFAULT_FORMAT, reset=True))
logger.addHandler(console_handler)


def execute(command: str) -> subprocess.Popen:
    logger.debug(f'Executing command: {command}')
    process = subprocess.Popen(command, shell=True)
    return process


def hash_val(input_string: str, siz: int = 1024) -> int:
    """Calculate the hash value of a string.

    Args:
        input_string (str): The string to be hashed.
        siz (int, optional): The size of the hash table. Defaults to 1024.

    Returns:
        int: The hash value of the string.
    """
    hash_value = sum(ord(x) for x in input_string)
    return hash_value % siz


def add_profile_to_aws_config(account_id: str, role: str, sso_url: str, default_region: str, sso_region: str,
                              dont_override: bool = False,
                              config_file_path: Optional[str] = None) -> str:
    """
    Add a profile to the AWS config file.

    Args:
        account_id (str): The AWS account ID.
        role (str): The role name.
        sso_url (str): The SSO start URL.
        default_region (str): The default region.
        sso_region (str): The SSO region.
        dont_override (bool, optional): Whether to override an existing profile. Defaults to False.
        config_file_path (str, optional): The path to the AWS config file. Defaults to '~/.aws/config'.

    Returns:
        str: The profile name.
    """
    config_file_path = config_file_path or os.path.join(str(Path.home()), '.aws', 'config')
    logger.debug(f'Adding profile to AWS config file: {account_id}-{role}')
    if not isinstance(account_id, str):
        raise TypeError("'account_id' must be a string.")
    if not isinstance(role, str):
        raise TypeError("'role' must be a string.")
    if not isinstance(sso_url, str):
        raise TypeError("'sso_url' must be a string.")
    if not isinstance(default_region, str):
        raise TypeError("'default_region' must be a string.")
    if not isinstance(sso_region, str):
        raise TypeError("'sso_region' must be a string.")

    if not os.path.exists(config_file_path):
        os.makedirs(os.path.dirname(config_file_path), exist_ok=True)

    parser = configparser.ConfigParser()
    parser.read(config_file_path)

    profile_name = f'{account_id}-{role}'
    section_name = f'profile {profile_name}'

    if section_name in parser.sections():
        if dont_override:
            return profile_name
    else:
        parser.add_section(section_name)

    parser.set(section_name, 'sso_start_url', sso_url)
    parser.set(section_name, 'sso_region', sso_region)
    parser.set(section_name, 'sso_account_id', account_id)
    parser.set(section_name, 'sso_role_name', role)
    parser.set(section_name, 'region', default_region)
    parser.set(section_name, 'output', 'json')

    with open(config_file_path, 'w') as config_file:
        parser.write(config_file)

    return profile_name


def get_home_directory() -> str:
    """Get the home directory.

    Returns:
        str: The home directory.
    """
    system = platform.system()
    if system == 'Linux' and os.getenv('SUDO_USER'):
        return os.path.expanduser(f'~{os.getenv("SUDO_USER")}')
    return str(Path.home())


def get_username() -> str:
    system = platform.system()
    if system == 'Linux':
        if username := os.getenv('SUDO_USER') or os.getenv('USER') or os.getenv('USERNAME'):
            return username

    return os.getlogin()


def validate_aws_installation() -> None:
    # pylint: disable=raise-missing-from
    logger.debug('Validating AWS CLI installation')
    try:
        aws_version = subprocess.check_output('aws --version', shell=True).decode('ascii').strip()
    except subprocess.CalledProcessError:
        raise Exception(
            'Please install aws-cli: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html')

    if not aws_version.startswith('aws-cli/2.'):
        raise Exception('Please update aws-cli to version 2 or higher: '
                        'https://docs.aws.amazon.com/cli/latest/userguide/cliv2-migration-instructions.html')
    elif int(aws_version.split('.')[1]) < 8:
        raise Exception('AWS cli version under 2.8 please update to the latest version: '
                        'https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html')


def validate_ssm_installation() -> None:
    # pylint: disable=raise-missing-from
    logger.debug('Validating SSM installation')
    try:
        ssm_plugin_output = subprocess.check_output('session-manager-plugin', shell=True).decode('ascii').strip()
        if not ssm_plugin_output.startswith('The Session Manager plugin was installed successfully'):
            raise Exception('Session Manager plugin not installed')
    except subprocess.CalledProcessError:
        raise Exception('Please install the Session Manager plugin for the AWS CLI: '
                        'https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html')


def validate_internet_connection() -> bool:
    logger.debug('Validating internet connection')
    try:
        urllib.request.urlopen('https://www.google.com')
        return True
    except Exception as e:
        raise Exception('No internet connection') from e


def validate_prerequisites() -> None:
    validate_internet_connection()
    validate_aws_installation()
    validate_ssm_installation()
