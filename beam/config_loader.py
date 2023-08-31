from dataclasses import dataclass, field
from typing import Optional

import yaml
from dataclasses_json import DataClassJsonMixin

from beam.aws.bastion import AwsBastion


@dataclass
class BeamEksConfig(DataClassJsonMixin):
    enabled: Optional[bool] = True
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class BeamRdsConfig(DataClassJsonMixin):
    enabled: Optional[bool] = True
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class BeamAwsConfig(DataClassJsonMixin):
    sso_url: str
    sso_region: str
    role: str
    accounts: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)


@dataclass
class BeamBastionConfig(DataClassJsonMixin):
    tags: dict[str, str] = field(default_factory=lambda: {'Name': '*bastion*'})

    @property
    def name(self) -> str:
        return self.tags.get('Name', '*bastion*')

    @property
    def other_tags(self) -> dict[str, str]:
        tags_without_name = self.tags.copy()
        tags_without_name.pop('Name')
        return tags_without_name


@dataclass
class BeamKubernetesConfig(DataClassJsonMixin):
    namespace: Optional[str] = 'default'


@dataclass
class BeamConfig(DataClassJsonMixin):
    # aws
    aws: BeamAwsConfig
    bastion: BeamBastionConfig
    kubernetes: BeamKubernetesConfig = field(default_factory=BeamKubernetesConfig)
    eks: BeamEksConfig = field(default_factory=BeamEksConfig)
    rds: BeamRdsConfig = field(default_factory=BeamRdsConfig)

    bastions: list[AwsBastion] = field(default_factory=list)

    @staticmethod
    def _parse_config(config: dict) -> 'BeamConfig':
        return BeamConfig(
            aws=BeamAwsConfig.from_dict(config['aws']),
            bastion=BeamBastionConfig.from_dict(config['bastion']),
            kubernetes=BeamKubernetesConfig.from_dict(config['kubernetes']),
            eks=BeamEksConfig.from_dict(config['eks']),
            rds=BeamRdsConfig.from_dict(config['rds']),
        )

    @staticmethod
    def load_config(config_path: str) -> 'BeamConfig':
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)

        try:
            return BeamConfig.from_dict(config)
        except KeyError as e:
            raise KeyError(f'Missing key in config file: {e}') from e
