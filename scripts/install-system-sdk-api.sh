#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"
tree="$RDKHM_OH_TREE"
generated="$tree/out/rdk_x5/sdk-interface/ets1.1/sdk-js"
api="$tree/out/rdk_x5/ohos_declaration/ets/ohos_declaration_ets"
sdk="$RDKHM_OH_SDK/ets"
test -f "$api/@ohos.app.ability.ServiceExtensionAbility.d.ts"
test -d "$sdk/api"
# The SDK generator converts source-only types before these declarations are installed.
cp -a "$api/." "$sdk/api/"
cp -a "$generated/kits/." "$sdk/kits/"
cp -a "$generated/arkts/." "$sdk/arkts/"
cp -a "$generated/api/@internal/component/ets/." "$sdk/component/"
compiler="$tree/developtools/ace_ets2bundle/compiler"
loader="$sdk/build-tools/ets-loader"
node="$tree/prebuilts/build-tools/common/nodejs/current/bin/node"
"$node" "$compiler/build_components_file.js" "$sdk/component" \
    "$loader/components" "$loader/form_components"
"$node" "$compiler/build_declarations_file.js" "$sdk/component" \
    "$loader/declarations" "$loader/lib" false
echo 'Installed source-generated system API declarations into the API 20 SDK'
