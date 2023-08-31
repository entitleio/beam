import platform
import re

from beam.exceptions import AdministratorRequiredError
from beam.utils import logger


def get_hosts_path() -> str:
    system = platform.system()
    if system == 'Windows':
        return r'C:\Windows\System32\drivers\etc\hosts'
    elif system in ['Linux', 'Darwin']:
        return '/etc/hosts'
    else:
        raise OSError(f'Unsupported system: {system}')


def edit_hosts_entry(host: str, hostname: str = '127.0.0.1') -> bool:
    hosts_path = get_hosts_path()
    logger.debug(f'Appending to hosts file ({hosts_path}): {hostname} {host}')

    try:
        # first try to open with read-only to check if editing is required
        # if yes, open with write permissions
        with open(hosts_path, 'r') as file:
            if re.search(rf'({hostname})\s({host})', file.read()):
                return True

        logger.debug(f"Host '{host}' not found in hosts file, adding it")

        with open(hosts_path, 'a') as file:
            file.write(f'{hostname} {host}\n')
        logger.debug(f"Host '{host}' added to hosts file")
    except PermissionError as e:
        logger.exception(f'Permission error while editing the hosts file ({hosts_path})')
        raise AdministratorRequiredError('Unable to edit hosts file.'
                                         'Please allow write permissions to the hosts file: sudo chmod 666 /etc/hosts'
                                         'or running as administrator (e.g. sudo beam run)') from e
    except IOError:
        logger.exception('Error while editing the hosts file')
        return False

    return True
