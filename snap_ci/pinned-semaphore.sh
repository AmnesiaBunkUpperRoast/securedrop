#!/bin/bash
# Pin commands to install vagrant, ansible, serverspec
# Pinning commands will ensure that they are run in each snap-ci stage.
# This is useful for two reasons:
#   * rerunning a single stage from a pipeline of many
#   * keeping the CI suite DRY

set -e
set -x
set -u

# Support Snap-CI cache directory, but also allow this script to be run locally.
tmp_dir="${SNAP_CACHE_DIR:-/tmp}"

# Find the root of the git repository. A simpler implementation
# would be `git rev-parse --show-toplevel`, but that must be run
# from inside the git repository, whereas the solution below is
# directory agnostic. Exporting this variable doesn't work in snapci,
# so it must be rerun in each stage.
repo_root=$( dirname "$( cd "$( dirname "${BASH_SOURCE[0]}"  )" && pwd )" )

# Cache and install Vagrant
vagrant_version="${vagrant_version:-1.7.2}"
vagrant_package="vagrant_${vagrant_version}_x86_64.deb"
vagrant_url="https://dl.bintray.com/mitchellh/vagrant/${vagrant_package}"

[[ -f "${tmp_dir}/${vagrant_package}" ]] || wget -q "$vagrant_url" -O "${tmp_dir}/${vagrant_package}"
[[ -x /usr/bin/vagrant ]] || sudo -E dpkg -i "${tmp_dir}/$vagrant_package"

# Install Vagrant plugins
vagrant plugin install vagrant-digitalocean
vagrant plugin install vagrant-hostmanager

# Install Ansible dependencies
sudo apt install -y python-pip
sudo apt install -y rubygems-integration
# Install Ansible via pip for fine-grained version control
sudo pip install ansible==1.9.0.1

# Install serverspec dependencies
cd "${repo_root}/spec_tests/" && bundle install
