import os
import pathlib

import pkg_resources
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


with pathlib.Path('requirements.txt').open() as requirements_txt:
    install_requires = [str(requirement).strip() for requirement in pkg_resources.parse_requirements(requirements_txt)
                        if not str(requirement).strip().startswith('#')]

setup(
    name='devcache',
    version='1.0.0',
    author='Patrick Cauthorn',
    author_email='patrick.cauthorn@gmail.com',
    description='Provides caching decorator to help speedup development',
    license='MIT',
    url='https://github.com/pcauthorn/devcache',
    install_requires=install_requires,
    packages=find_packages(exclude=('tests',)),
    long_description=read('README.md'),
    classifiers=[
        'Topic :: Utilities',
        'License :: OSI Approved :: MIT License',
    ],
)
