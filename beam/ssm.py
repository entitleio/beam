import socket
import subprocess
from typing import Optional

import boto3

from beam.utils import execute, logger


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
        >>> start_ssm_forwarding_session('us-west-2', 'i-0123456789abcdef0', 'localhost', 22, 2222, 'my-profile')
        True
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
        process = execute(
            f'aws ssm --profile {profile} --region {region} start-session --target'
            f' {instance_id} --document-name AWS-StartPortForwardingSessionToRemoteHost '
            f'--parameters "{{\\"host\\": [ \\"{host}\\" ], \\"portNumber\\": [ \\"{remote_port}\\" ],'
            f' \\"localPortNumber\\": [ \\"{local_port}\\" ] }}"')
        return process
    except subprocess.CalledProcessError as e:
        logger.error(f'Error executing command: {e.cmd}. Return code: {e.returncode}. Output: {e.output}')

    ec2 = boto3.client('ec2', region_name=region)
    try:
        ec2.describe_instances(InstanceIds=[instance_id])
    except ec2.exceptions.ClientError as e:
        raise ValueError('instance_id is not a valid AWS identifier') from e

    try:
        socket.gethostbyname(host)
    except socket.gaierror as e:
        raise ValueError('Invalid hostname or IP address') from e

    return None
