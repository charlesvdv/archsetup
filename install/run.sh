#/usr/bin/env bash

set -e

# TODO: it would be better to build directly an ISO with the patched 
# archinstall.

pip show archinstall 2&> /dev/null && echo 'uninstall archinstall before running this script' && exit 1

if [ "$#" -ne 1 ]; then
    echo "usage: $0 <script name>"
    exit 1
fi

custom_install_dir=$(dirname "$0")
tmpdir=$(mktemp -d)

# TODO: use latest tag as soon as 2.2.0 is released
git clone https://github.com/archlinux/archinstall $tmpdir

cp $custom_install_dir/*.py $tmpdir/examples

pushd "$tmpdir"
python setup.py install
popd

rm -rf $tmpdir

python -m archinstall --script $1