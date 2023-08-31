# type: ignore
import setuptools

import versioneer

with open('requirements.txt', 'r', encoding='utf-8') as fh:
    requirements = [line.strip() for line in fh]

setuptools.setup(
    name='beam',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    install_requires=requirements,
)
