#!/usr/bin/python3
import functools
import logging
import os
import sys
from typing import Any, Callable

import aws_sso_lib
import click
import yaml
from click import Context
from rich import print  # pylint: disable=redefined-builtin
from rich.align import Align
from rich.panel import Panel
from rich.pretty import Pretty

from beam import settings, __version__
from beam.aws.utils import AwsOrganization
from beam.config_loader import BeamConfig
from beam.runner import BeamRunner
from beam.selector import ask_for_config
from beam.utils import logger, get_home_directory, validate_prerequisites

DEFAULT_CONFIG_DIRECTORY = os.path.join(get_home_directory(), '.beam', 'config.yaml')


def common_params(func: Callable) -> Callable:
    @click.option('--debug', '--verbose', default=False, help='Print debug logs', is_flag=True)
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:  # type: ignore
        if 'debug' in kwargs:
            if kwargs.get('debug', False):
                logger.setLevel(logging.DEBUG)
                settings.debug = True

            else:
                logger.setLevel(logging.WARNING)
            kwargs.pop('debug')

        return func(*args, **kwargs)

    return wrapper


@click.group(invoke_without_command=True)
@click.option('--version', help='Show version', is_flag=True)
@click.pass_context
def cli(ctx: Context = None, version: bool = False) -> None:  # pylint: disable=redefined-outer-name
    if version:
        print_version()
        return

    if ctx.invoked_subcommand is None:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()


@cli.command()
@click.option('--config', '-c', default=DEFAULT_CONFIG_DIRECTORY, help='Path to config file to generate')
@click.option('--sso-url', '-c', help='AWS SSO URL')
@click.option('--sso-region', '-c', help='AWS SSO Region')
@common_params
def configure(config: str, sso_url: str, sso_region: str) -> None:
    validate_prerequisites_and_exit()

    config = os.path.realpath(config)
    try:
        beam_config = ask_for_config(config_path=config, sso_url=sso_url, sso_region=sso_region)
    except KeyboardInterrupt:
        return

    if not beam_config:
        return

    os.makedirs(os.path.dirname(config), exist_ok=True)
    with open(config, 'w') as file:
        yaml.dump(beam_config.to_dict(), file)

    print(f'[bold green]:heavy_check_mark:[/bold green] Config saved to [bold italic bright_cyan]{config}[/bold italic bright_cyan]\n')


@cli.command()
@click.option('--config', '-c', default=DEFAULT_CONFIG_DIRECTORY, help='Path to config file')
@click.option('--force-scan', '-f', default=False, help='Force scan of all accounts', is_flag=True)
@click.option('--eks/--no-eks', default=True, help='Connect to EKS clusters')
@click.option('--rds/--no-rds', default=True, help='Connect to RDS clusters')
@common_params
def run(config: str, force_scan: bool, eks: bool, rds: bool) -> None:
    validate_prerequisites_and_exit()

    config = os.path.realpath(config)
    print(Panel(
        Align.center(
            '[bold yellow3]Beam[/bold yellow3] by [bold magenta]Entitle[/bold magenta] :comet:'
        ), border_style='yellow3'))

    # TODO: Create custom Command class and manage logs from there, support multi log levels
    # see here https://github.com/pallets/click/issues/66#issuecomment-674322963

    try:
        with open(config, 'r') as file:
            config_dict = yaml.safe_load(file)
        beam_config = BeamConfig.from_dict(config_dict)
    except FileNotFoundError:
        logger.error(f'Config file not found: {config}', exc_info=True if settings.debug else None)
        return
    except Exception as e:
        logger.error(f'Failed to load Beam config: {e}', exc_info=True if settings.debug else None)
        return

    if settings.debug:
        print(Panel.fit(Pretty(beam_config), title=config, border_style='white'))

    organization = AwsOrganization(beam_config.aws.sso_url, beam_config.aws.sso_region)
    permission_set = beam_config.aws.role  # TODO: ADD TO SELECTOR TO SELECT PS FOR EACH ACCOUNT OR ALL OF THEM

    aws_sso_lib.login(beam_config.aws.sso_url, beam_config.aws.sso_region)

    beam_runner = BeamRunner(beam_config, config, organization, permission_set)

    if force_scan or not beam_config.bastions:
        bastions = beam_runner.scan_resources()
    else:
        bastions = beam_config.bastions

    # print endpoints
    rds_endpoints = [f'{rds_instance.endpoint}:{rds_instance.local_port}' for bastion in bastions for rds_instance in bastion.rds_instances]
    endpoints_str = '\n'.join([f'[bold green]{endpoint}[/bold green]' for endpoint in rds_endpoints])
    print(Panel.fit(f'{endpoints_str}', title='RDS (Database) Endpoints', border_style='green', padding=(1, 2, 1, 2)))

    processes = beam_runner.connect_to_resources(bastions, eks, rds)

    logger.debug('Finished Beam')

    try:
        [process.wait() for process in processes]
    except KeyboardInterrupt:
        logger.debug('Exiting Beam')
        for process in processes:
            process.kill()


@cli.command()
@common_params
def stop() -> None:
    pass


@cli.command()
def version() -> None:
    print_version()


def print_version() -> None:
    print(f'[bold yellow3]Beam[/bold yellow3] [white]{__version__}[/white] by [bold magenta]Entitle[/bold magenta] :comet:')


def validate_prerequisites_and_exit() -> None:
    try:
        validate_prerequisites()
    except Exception as e:
        if settings.debug:
            logger.exception(f'Failed to validate prerequisites: {e}')
        else:
            print(f'[bold red]Error:[/bold red] {e}')
        sys.exit(1)


def setup_yaml() -> None:
    def represent_none(self, _) -> Any:  # type: ignore
        return self.represent_scalar('tag:yaml.org,2002:null', '')

    yaml.add_representer(type(None), represent_none)


def main() -> None:
    setup_yaml()
    cli()


if __name__ == '__main__':
    cli()
