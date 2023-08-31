import os

from dynaconf import Dynaconf

ROOT = os.path.dirname(__file__)

settings = Dynaconf(
    root_path=os.path.dirname(ROOT),
    envvar_prefix='BEAM',
    settings_files=['beam/settings.toml'],
    load_dotenv=True,
)
