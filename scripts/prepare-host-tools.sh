#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$workspace/out/host-debs" "$workspace/out/host-tools"
cd "$workspace/out/host-debs"
# Ubuntu 22.04 build host. Extract privately; do not install host packages.
apt-get download ruby3.0 libruby3.0 ruby-webrick ruby-net-telnet ruby-xmlrpc ruby-rubygems rake
for package in ./*.deb; do
    dpkg-deb -x "$package" "$workspace/out/host-tools"
done
sha256sum ./*.deb > "$workspace/out/host-tools/debs.sha256"
bash "$workspace/scripts/ruby" -ryaml -rerb -rostruct -e 'puts RUBY_VERSION'
