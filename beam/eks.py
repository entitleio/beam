import os
import platform
from pathlib import Path
from typing import Optional

import boto3
import yaml


def update_kubeconfig(boto3_session: boto3.Session,
                      cluster_name: str,
                      cluster_region: str,
                      cluster_profile: str,
                      local_api_server_port: int,
                      kubeconfig_path: Optional[str] = None,
                      default_namespace: str = 'default') -> None:
    if not kubeconfig_path:
        kubeconfig_path = str(Path.home() / '.kube' / 'config')
    eks_client = boto3_session.client('eks')
    eks_cluster = eks_client.describe_cluster(name=cluster_name)['cluster']

    if os.path.isfile(kubeconfig_path):
        with open(kubeconfig_path, 'r') as file:
            kubeconfig = yaml.safe_load(file) or {}
    else:
        os.makedirs(os.path.dirname(kubeconfig_path), exist_ok=True)
        with open(kubeconfig_path, 'w+'):
            # set permissions to 600 and ownership to (real) current user
            os.chmod(kubeconfig_path, 0o600)
            username = os.getlogin()
            if platform.system() != 'Windows':
                from pwd import getpwnam  # this import doesn't work on Windows  # pylint: disable=import-outside-toplevel
                uid = getpwnam(username).pw_uid
                gid = getpwnam(username).pw_uid
                os.chown(kubeconfig_path, uid, gid)
            kubeconfig = {}

    # clusters
    kubeconfig_clusters = kubeconfig.get('clusters', [])
    existing_cluster_without_target = [cluster for cluster in kubeconfig_clusters if
                                       not cluster.get('cluster', {}).get('server', '').startswith(eks_cluster['endpoint'])]

    account_id = eks_cluster['arn'].split(':')[4]
    cluster_name_in_kubeconfig = f'{account_id}:{cluster_region}:{cluster_name}'
    new_cluster = {
        'cluster': {
            'server': f"{eks_cluster['endpoint']}:{local_api_server_port}",
            'certificate-authority-data': eks_cluster['certificateAuthority']['data']
        },
        'name': cluster_name_in_kubeconfig
    }

    new_clusters = existing_cluster_without_target + [new_cluster]

    # contexts
    kubeconfig_contexts = kubeconfig.get('contexts', [])
    existing_contexts_without_target = [context for context in kubeconfig_contexts if
                                        not context.get('context', {}).get('cluster', '').startswith(cluster_name_in_kubeconfig)]
    existing_context: Optional[dict] = next((context for context in kubeconfig_contexts if
                                             context.get('context', {}).get('cluster', '').startswith(cluster_name_in_kubeconfig)), None)
    new_context = {
        'context': {
            'cluster': cluster_name_in_kubeconfig,
            'user': cluster_name_in_kubeconfig,
            'namespace': default_namespace,
        },
        'name': cluster_name_in_kubeconfig
    }

    # copy current namespace if set
    if namespace := existing_context and existing_context.get('context', {}).get('namespace'):
        new_context['context']['namespace'] = namespace  # type: ignore

    new_contexts = existing_contexts_without_target + [new_context]

    # users
    kubeconfig_users = kubeconfig.get('users', [])
    existing_users_without_target = [user for user in kubeconfig_users if not user.get('name').startswith(cluster_name_in_kubeconfig)]
    new_user = {
        'name': cluster_name_in_kubeconfig,
        'user': {
            'exec': {
                'apiVersion': 'client.authentication.k8s.io/v1beta1',
                'command': 'aws',
                'args': [
                    '--region', cluster_region, 'eks', 'get-token', '--cluster-name', cluster_name, '--output', 'json'
                ],
                'env': [
                    {'name': 'AWS_PROFILE', 'value': cluster_profile}
                ]
            }
        }
    }
    new_users = existing_users_without_target + [new_user]

    new_kubeconfig_file = {}
    kubeconfig_declarations = {
        'apiVersion': 'v1',
        'kind': 'Config',
        'current-context': cluster_name_in_kubeconfig,
        'preferences': {},
    }
    new_kubeconfig_file.update(kubeconfig_declarations)
    new_kubeconfig_file['clusters'] = new_clusters
    new_kubeconfig_file['contexts'] = new_contexts
    new_kubeconfig_file['users'] = new_users

    config_text = yaml.dump(new_kubeconfig_file, default_flow_style=False)
    with open(kubeconfig_path, 'w+') as file:
        file.write(config_text)
