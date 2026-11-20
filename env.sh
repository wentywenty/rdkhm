#!/usr/bin/env bash
# Shared environment for build, package and deploy entry points.
# Paths are derived from the workspace; explicit environment variables win.
rdkhm_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
workspace="$rdkhm_root"
# shellcheck source=../scripts/workspace-env.sh
source "$rdkhm_root/scripts/workspace-env.sh"

export RDKHM_ROOT="$rdkhm_root"
export RDKHM_TOOLS_DIR="${RDKHM_TOOLS_DIR:-$rdkhm_root/thirdparty}"
export RDKHM_OH_TREE="${RDKHM_OH_TREE:-$rdkhm_root/sources/oh/openharmony-full}"
export RDKHM_OH_DEPS_TREE="${RDKHM_OH_DEPS_TREE:-$rdkhm_root/sources/oh/openharmony}"
export RDKHM_KERNEL_TREE="${RDKHM_KERNEL_TREE:-$rdkhm_root/sources/rdk/x5-kernel}"
export RDKHM_OH_SDK="${RDKHM_OH_SDK:-$RDKHM_OH_TREE/prebuilts/ohos-sdk/linux/20}"
export RDKHM_HDC="${RDKHM_HDC:-$RDKHM_OH_SDK/toolchains/hdc}"
export RDKHM_COMMAND_LINE_TOOLS="${RDKHM_COMMAND_LINE_TOOLS:-$RDKHM_TOOLS_DIR/toolchains/command-line-tools-26}"
export RDKHM_CACHE_DIR="${RDKHM_CACHE_DIR:-$RDKHM_TOOLS_DIR/downloads}"
export RDKHM_WS73_ARCHIVE="${RDKHM_WS73_ARCHIVE:-$RDKHM_CACHE_DIR/ws73_sdk_linux_WS73_1.10.110_patched.tar.gz}"
export CROSS_COMPILE="${CROSS_COMPILE:-$RDKHM_TOOLS_DIR/toolchains/gcc-arm-11.2/bin/aarch64-none-linux-gnu-}"
