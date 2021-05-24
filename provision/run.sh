#!/usr/bin/env bash

set -e 

ansible-playbook -i inventory.yml --ask-become-pass thinkpad-t495.yml