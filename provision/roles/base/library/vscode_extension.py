#!/usr/bin/python

# Copyright: (c) 2021, Charles Vandevoorde
# MIT license
__metaclass__ = type

DOCUMENTATION = r'''
---
module: vscode_extension

short_description: Manage Visual Studio Code (vscode) extensions

version_added: "0.1.0"

description:

options:
    name:
        description:
            - Name or list of names of the extensions to build.
        aliases: [ extension ]
        type: list
        elements: str

author:
    - Charles Vandevoorde (@charlesvdv)
'''

EXAMPLES = r'''
# Install an extension
- name: Install golang extension
  aur_build:
    name: golang.go
'''

RETURN = r'''
'''

from typing import Set

from ansible.module_utils.basic import AnsibleModule

def list_installed_extensions(module: AnsibleModule) -> Set[str]:
    _, stdout, _ = module.run_command(['code', '--list-extensions'], check_rc=True)
    return set(stdout.splitlines())

def install_extension(module: AnsibleModule, extension: str):
    module.run_command(['code', '--install-extension', extension], check_rc=True)

def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='list', elements='str', aliases=['extension']),
        ),
        supports_check_mode=True,
    )

    installed_extensions = list_installed_extensions(module)

    not_installed = set(module.params.get('name')) - installed_extensions
    changed = len(not_installed) != 0

    if module.check_mode:
        module.exit_json(changed=changed)


    for extension in not_installed:
        install_extension(module, extension)

    module.exit_json(changed=changed)



if __name__ == "__main__":
    main()