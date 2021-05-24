#!/usr/bin/python

# Copyright: (c) 2021, Charles Vandevoorde
# MIT license
__metaclass__ = type

DOCUMENTATION = r'''
---
module: aur_build

short_description: Build AUR packages and add them to a local pacman database

version_added: "0.1.0"

description:
    - "This module do not install packages but only makes them availabe for pacman to install them"
    - "This module must not run as root"

options:
    name:
        description:
            - Name or list of names of the package(s) or file(s) to build.
        aliases: [ package, pkg ]
        type: list
        elements: str
    database:
        description:
            - The database the built package(s) will be added to.
        type: str
        default: aur

author:
    - Charles Vandevoorde (@charlesvdv)
'''

EXAMPLES = r'''
# Build one AUR package
- name: Build spotify package
  aur_build:
    name: spotify

# Build multiple AUR packages
- name: Build a few package
  aur_build:
    name:
      - spotify
      - autojump

# Build a AUR package and 
- name: Build a package and add it to a custom database
  aur_build:
    name: spotify
    database: custom_db
'''

RETURN = r'''
'''

from typing import List, Set, Iterable, Dict, Optional, Tuple
import itertools
import tempfile
import pathlib
import urllib.parse
import re
import shutil
import os.path
import tarfile
import enum
import json

from ansible.module_utils.basic import AnsibleModule
import ansible.module_utils.urls as urls


AURWEB_URL = 'https://aur.archlinux.org/'

class DependencyConstraint(enum.Enum):
    GREATER_OR_EQUAL = '>='
    LESS_OR_EQUAL = '<='
    EQUAL = '='
    GREATER = '>'
    LESS = '<'

class Dependency:
    name: str
    constraint: Optional[DependencyConstraint]
    constraint_version: Optional[str]

    def __init__(self, dep: str):
        for constraint in DependencyConstraint:
            if constraint.value in dep:
                self.constraint = constraint
                split = dep.split(constraint.value)
                self.name = split[0]
                self.constraint_version = split[1]
                break
        else:
            self.name = dep


class Package:
    name: str
    url: str
    version: str
    depends: List[Dependency]
    make_depends: List[Dependency]
    check_depends: List[Dependency]

    def __repr__(self) -> str:
        return f'Package(name={self.name})'

    def __str__(self) -> str:
        return f'Package(name={self.name})'


def strip_root_directory_from_path(inputpath):
    # /dir/file -> file
    # /dirA/dirB/file -> dirB/file
    path = pathlib.Path(inputpath)
    if path.is_absolute():
        path.relative_to('/')
    if len(path.parts) > 1:
        path = pathlib.Path(*path.parts[1:])
    return path

def download_pkginfo(module: AnsibleModule, package: Package, path: str) -> None:
    request_url = AURWEB_URL + package.url

    tar_file = urls.fetch_file(module, request_url)
    with tarfile.open(tar_file, 'r:*') as archivefile:
            for member in archivefile.getmembers():
                if member.isfile():
                    # remove the top directory before extracting
                    member.path = strip_root_directory_from_path(member.path)
                    archivefile.extract(member, path=path)

def format_info_url_request(packages: List[str]) -> str:
    raw_query_strings = [('v', 5), ('type', 'info')]
    for package in packages:
        raw_query_strings.append(('arg[]', package))

    query_strings = urllib.parse.urlencode(raw_query_strings)

    return f'{AURWEB_URL}/rpc?{query_strings}'

def get_packages_metadata(module: AnsibleModule, packages: List[str]) -> List[Package]:
    request_url: str = format_info_url_request(packages)
    resp, info = urls.fetch_url(module, request_url)
    if info['status'] != 200:
        raise RuntimeError(f'invalid aurweb rpc response: {info}')
    data = json.loads(resp.read().decode('utf-8'))
    # with urllib.request.urlopen(request_url) as f:
    #     data = json.loads(f.read().decode('utf-8'))
    if data['type'] != 'multiinfo':
        raise RuntimeError(f'invalid aurweb rpc response: {data}')

    aur_packages: List[Package] = []
    for package_info in data['results']:
        aur_package = Package()
        aur_package.name = package_info['Name']
        aur_package.version = package_info['Version']
        aur_package.url = package_info['URLPath']
        aur_package.depends = [ Dependency(x) for x in package_info.get('Depends', []) ]
        aur_package.make_depends = [ Dependency(x) for x in package_info.get('MakeDepends', []) ]
        aur_package.check_depends = [ Dependency(x) for x in package_info.get('CheckDepends', []) ]

        aur_packages.append(aur_package)

    return aur_packages



class PacmanConfig:
    _sections: Dict[str, Dict[str, List[str]]]
    _current_section: Optional[str]
    SECTION_RE = re.compile(r'^\[(\w+)\]\s+$')

    def __init__(self, path='/etc/pacman.conf'):
        self._current_section = None
        self._sections = dict()
        self._parse(path)

    def _parse(self, path):
        with open(path, 'r') as f:
            for line in f.readlines():
                if line.startswith('#') or line.strip() == '':
                    # ignore comments
                    continue
                if (match := self.SECTION_RE.match(line)) is not None:
                    self._current_section = match.group(1)
                    self._sections[self._current_section] = dict()
                elif line.startswith('Include'):
                    chuncks = line.split('=')
                    self._parse(chuncks[1].strip())
                elif self._current_section:
                    chuncks = line.split('=', 2)
                    key, value = chuncks[0].strip(), None
                    if len(chuncks) == 2:
                        value = chuncks[1].strip()
                    if not key in self._sections[self._current_section]:
                        self._sections[self._current_section][key] = list()
                    self._sections[self._current_section][key].append(value)
    
    def get_section(self, name: str) -> Optional[Dict[str, List[str]]]:
        return self._sections.get(name)


class PacmanDatabase:
    _name: str
    _directory: str
    _db_path: str
    _module: AnsibleModule

    def __init__(self, module: AnsibleModule, config: PacmanConfig, name: str) -> None:
        self._module = module
        self._name = name
        self._directory = self._get_database_directory(config, name)
        self._db_path = self._get_database_path(self._directory, self._name)

    def _get_database_directory(self, config: PacmanConfig, database_name: str) -> str:
        database_config = config.get_section(database_name)
        if not database_config:
            raise ValueError(f'unknow database: {database_name}')
        server = database_config.get('Server')
        if not server or len(server) != 1 or not server[0].startswith('file://'):
            raise ValueError(f'invalid database configuration for {database_name}')
        return server[0].removeprefix('file://')

    def _get_database_path(self, database_directory: str, database_name: str) -> str:
        return os.path.realpath(f'{database_directory}/{database_name}.db') 

    def install_package(self, package_path: str):
        self._module.run_command(['repo-add', self._db_path, package_path], check_rc=True)
        shutil.move(package_path, self._directory)
        # shutil.move(sig_path, self._directory)

    def get_name(self) -> str:
        return self._name


def is_package_installed(module: AnsibleModule, package: str) -> bool: 
    rc, _, _ = exec_pacman(module, ['-Q', package], check_rc=False)
    return rc == 0

def get_available_package_version(module: AnsibleModule, package: str) -> str:
    _, stdout, _ = exec_pacman(module, ['-Ss', f'^{package}$'])

    # Example of output for the command `pacman -Ss ^python$`:
    #
    # extra/python 3.9.3-1 [installed]
    #   Next generation of the python high-level scripting language
    #
    # We want to extract the '3.9.3-1' token

    first_line = stdout.split('\n')[0]
    version = first_line.split(' ')[1].strip()

    return version

def exec_pacman(module: AnsibleModule, options: List[str], check_rc=True) -> Tuple[int, str, str]:
    command = ['pacman']
    command.extend(options)
    result, stdout, stderr = module.run_command(command, check_rc=check_rc)
    return (result, stdout, stderr)

def is_package_available(module: AnsibleModule, package: str) -> bool:
    rc, _, _ = exec_pacman(module, ['-Ss', f'^{package}$'], check_rc=False)
    return rc == 0

def get_package_database(module: AnsibleModule, package: str) -> str:
    _, stdout, _ = exec_pacman(module, ['-Ss', f'^{package}$'])

    # Example of output for the command `pacman -Ss ^python$`:
    #
    # extra/python 3.9.3-1 [installed]
    #   Next generation of the python high-level scripting language
    #
    # We want to extract the 'extra' token

    first_line = stdout.split('\n')[0]
    first_token = first_line.split(' ')[0]
    database_name = first_token.split('/')[0]

    return database_name.strip()

class Resolver: 
    """
    Resolver does the dependency resolution for AUR packages.
    For this case, the resolution is a bit specific because only AUR dependencies 
    will be resolved. Pacman will handle the dependency resolution for the rest of the 
    packages.
    """

    _packages_to_resolve: List[str]
    _packages_to_build: Set[Package]
    _packages_already_checked: Set[str]
    _aur_database: str
    _module: AnsibleModule

    def __init__(self, module: AnsibleModule, aur_database: str) -> None:
        self._module = module
        self._packages_to_resolve = []
        self._packages_to_build = set()
        self._packages_already_checked = set()
        self._aur_database = aur_database

    def resolve(self, packages: List[str]) -> Set[Package]:
        self._packages_to_resolve.extend(packages)
        self._resolve()
        return self._packages_to_build

    def _resolve(self):
        while self._packages_to_resolve:
            package_metadatas = get_packages_metadata(self._module, self._packages_to_resolve)
            packages_to_build = [ package for package in package_metadatas if self._should_build(package) ]
            self._packages_to_build.update(packages_to_build)
            self._packages_already_checked.update([ package.name for package in packages_to_build ])

            dependencies_to_resolve: List[Dependency] = list(itertools.chain.from_iterable([ package.depends for package in packages_to_build ]))

            self._packages_to_resolve = [ dep.name for dep in dependencies_to_resolve if self._should_resolve(dep.name) ]
            self._packages_already_checked.update(dependencies_to_resolve)

    def _should_build(self, package: Package) -> bool:
        if not is_package_available(self._module, package.name):
            return True

        # If a package has a different version than the version installed. It probably 
        # means the installed version is out-of-date.
        # There may be a better heuristic...
        if package.version != get_available_package_version(self._module, package.name):
            return True
        
        return False

    def _should_resolve(self, package: str) -> bool:
        # Skip if we already checked the package...
        if package in self._packages_already_checked:
            return False

        # If the package is not available in any pacman database, it probably means
        # it will be available in AUR.
        if not is_package_available(self._module, package):
            return True

        # If the package is already in the AUR database we populate, it should be probably 
        # checked for an update.
        if self._aur_database == get_package_database(self._module, package):
            return True

        return False

class Builder:
    _package: Package
    _module: AnsibleModule

    def __init__(self, module: AnsibleModule, package: Package):
        self._package = package
        self._module = module

    def __enter__(self):
        self._builddir = tempfile.TemporaryDirectory()
        return self

    def __exit__(self, type, value, traceback):
        self._builddir.cleanup()

    def build(self) -> None:
        self._check_build_requirement()
        download_pkginfo(self._module, self._package, self._builddir.name)
        self._makepkg()

    def get_package(self) -> str:
        builddir = pathlib.Path(self._builddir.name)
        possible_packages = list(builddir.glob('*.pkg.*'))
        if len(possible_packages) != 1:
            raise ValueError(f'Too much possible package files: {possible_packages}')
        return str(possible_packages[0])

    def get_sig_file(self) -> str:
        builddir = pathlib.Path(self._builddir.name)
        possible_sigfile = list(builddir.glob('*.sig'))
        if len(possible_sigfile) != 1:
            raise ValueError(f'Too much possible sig files: {possible_sigfile}')
        return str(possible_sigfile[0])


    def _check_build_requirement(self):
        def check_dependencies(deps: List[Dependency]) -> None:
            for dep in deps:
                if not is_package_installed(self._module, dep.name):
                    raise ValueError(f'package {dep.name} is missing to build the required AUR packages')

        check_dependencies(self._package.make_depends)
        check_dependencies(self._package.check_depends)


    def _makepkg(self):
        self._module.run_command(['makepkg', '--clean', '--noprogressbar', '--nodeps'], check_rc=True, cwd=self._builddir.name)

def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='list', elements='str', aliases=['pkg', 'package']),
            database=dict(type='str', default='aur'),
        ),
        supports_check_mode=True,
    )

    config = PacmanConfig()
    database = PacmanDatabase(module, config, module.params.get('database'))

    resolver = Resolver(module, database.get_name())
    packages_to_build = resolver.resolve(module.params.get('name'))
    changed: bool = len(packages_to_build) != 0

    if module.check_mode:
        module.exit_json(changed=changed)

    for package in packages_to_build:
        with Builder(module, package) as builder:
            builder.build()
            database.install_package(builder.get_package())

    module.exit_json(changed=changed)


if __name__ == '__main__':
    main()