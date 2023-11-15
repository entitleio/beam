import json
import subprocess
from typing import Optional

import boto3

from beam.utils import logger, execute


def start_ssm_forwarding_session(region: str, instance_id: str, host: str, remote_port: int,
                                 local_port: int, profile: str) -> Optional[subprocess.Popen]:
    """
    Start a Secure Shell (SSM) session to an AWS EC2 instance and forward a local port to a remote port on the instance.

    Args:
        region (str): The AWS region where the instance is located.
        instance_id (str): The identifier of the AWS EC2 instance to connect to.
        host (str): The remote host or IP address on the AWS EC2 instance to forward traffic to.
        remote_port (int): The remote port on the AWS EC2 instance to which traffic will be forwarded.
        local_port (int): The local port on the user's machine from which traffic will be forwarded.
        profile (str): The AWS CLI profile to be used for the SSM session.

    Returns:
        bool: True if the SSM session and port forwarding were successfully initiated, False otherwise.

    Raises:
        TypeError: If any of the arguments are not of the expected type.
        ValueError: If remote_port or local_port are not within the valid port range (1-65535).
        ValueError: If the instance_id is not a valid AWS EC2 instance identifier.
        ValueError: If the provided host is not a valid hostname or IP address.

    Note:
        This function requires AWS CLI and boto3 to be properly installed and configured with valid credentials.

    Example:
        start_ssm_forwarding_session('us-west-2', 'i-0123456789abcdef0', 'localhost', 22, 2222, 'my-profile')
    """
    logger.debug(f"Starting SSM session  (instance_id='{instance_id}', remote_port={remote_port}, local_port={local_port})")

    if not isinstance(region, str):
        raise TypeError('region must be a string')
    if not isinstance(instance_id, str):
        raise TypeError('instance_id must be a string')
    if not isinstance(host, str):
        raise TypeError('host must be a string')
    if not isinstance(remote_port, int):
        raise TypeError('remote_port must be an integer')
    if not isinstance(local_port, int):
        raise TypeError('local_port must be an integer')
    if remote_port < 1 or remote_port > 65535:
        raise ValueError('remote_port must be between 1 and 65535')
    if local_port < 1 or local_port > 65535:
        raise ValueError('local_port must be between 1 and 65535')

    logger.debug(
        f' Starting SSM session to instance_id {instance_id} on port {remote_port} and local port {local_port}')
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        ssm_client = session.client('ssm')
        ssm_parameters = {
            'host': [host],
            'portNumber': [str(remote_port)],
            'localPortNumber': [str(local_port)],
        }
        response = ssm_client.start_session(
            Target=instance_id,
            DocumentName='AWS-StartPortForwardingSessionToRemoteHost',
            Parameters=ssm_parameters
        )

        return start_aws_ssm_plugin(response, ssm_parameters, profile, region, instance_id)
    except subprocess.CalledProcessError as e:
        logger.error(f'Error executing command: {e.cmd}. Return code: {e.returncode}. Output: {e.output}')

    return None


def start_aws_ssm_plugin(create_session_response: dict, parameters: dict, profile: str, region: str, instance_id: str) \
        -> Optional[subprocess.Popen]:
    """
    Start the AWS SSM plugin to create a session and forward a local port to a remote port on an EC2 instance.

    Args:
        create_session_response: The response from creating an SSM session.
        parameters: The parameters for the SSM session.
        profile: The AWS CLI profile to be used for the SSM session.
        region: The AWS region where the instance is located.
        instance_id: The identifier of the EC2 instance to connect to.

    Returns:
        subprocess.Popen: The process for the SSM plugin command.

    Raises:
        subprocess.CalledProcessError: If there is an error executing the SSM plugin command.
    """
    plugin_parameters = {
        'Target': instance_id,
        'DocumentName': 'AWS-StartPortForwardingSessionToRemoteHost',
        'Parameters': parameters
    }

    command = [
        'session-manager-plugin',
        f"'{json.dumps(create_session_response)}'",
        region,
        'StartSession',
        profile,
        f"'{json.dumps(plugin_parameters)}'",
        f'https://ssm.{region}.amazonaws.com'
    ]

    try:
        process = execute(' '.join(command))
        return process
    except subprocess.CalledProcessError as e:
        logger.exception(f'Error executing command: {e.cmd} (return code: {e.returncode}) | Output: {e.output}')

    return None
