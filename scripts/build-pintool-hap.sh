#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/env.sh"

app="$workspace/apps/rdkhm-pintool"
src="$workspace/out/pintool-src"
sdk_home=$(python3 "$workspace/scripts/sdk-home.py")
node_dir="$RDKHM_OH_TREE/prebuilts/build-tools/common/nodejs/current"
hvigor="$RDKHM_COMMAND_LINE_TOOLS/command-line-tools/bin/hvigorw"
sign_tool="$RDKHM_OH_SDK/toolchains/lib/hap-sign-tool.jar"
keystore="$RDKHM_OH_SDK/toolchains/lib/OpenHarmony.p12"
template="$RDKHM_OH_SDK/toolchains/lib/UnsgnedReleasedProfileTemplate.json"
output="$workspace/out/haps/rdkhm_pintool.hap"

for path in "$app" "$hvigor" "$sign_tool" "$keystore" "$template" "$node_dir/bin/node"; do
    [[ -e "$path" ]] || { echo "Missing build input: $path" >&2; exit 1; }
done
command -v java >/dev/null || { echo "java is required to sign the HAP" >&2; exit 1; }
mkdir -p "$workspace/out/logs" "$workspace/out/haps"
rm -rf "$src"
cp -a "$app" "$src"
python3 "$workspace/scripts/gen-pin-data.py" \
    "$workspace/config/gpio/rdk_x5_40pin.json" \
    "$src/entry/src/main/ets/common/PinData.ets"
cat > "$src/hvigor/hvigor-config.json5" <<CONFIG
{
  "modelVersion": "6.0.2",
  "dependencies": {
    "@ohos/hvigor-ohos-plugin": "file:$RDKHM_COMMAND_LINE_TOOLS/command-line-tools/hvigor/hvigor-ohos-plugin"
  }
}
CONFIG
cat > "$src/local.properties" <<PROPERTIES
sdk.dir=$sdk_home
nodejs.dir=$node_dir
PROPERTIES

(
    cd "$src"
    PATH="$node_dir/bin:$PATH" NODE_HOME="$node_dir" \
    OHOS_BASE_SDK_HOME="$sdk_home" OHOS_SDK_HOME="$sdk_home" \
        "$hvigor" assembleHap --mode module -p product=default -p debuggable=false --no-daemon
) 2>&1 | tee "$workspace/out/logs/build-pintool-hap.log"

unsigned=$(find "$src/entry/build/default/outputs" -name '*-unsigned.hap' | head -1)
[[ -n "$unsigned" ]] || { echo "No unsigned HAP produced" >&2; exit 1; }

python3 - "$template" "$workspace/out/pintool-profile.json" "$workspace/out/pintool-app.pem" "$RDKHM_OH_SDK/toolchains/lib/OpenHarmonyProfileRelease.pem" <<'PY'
import json
import sys
import time
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
data["bundle-info"]["bundle-name"] = "com.rdkhm.pintool"
now = int(time.time())
data["validity"] = {"not-before": now - 86400, "not-after": now + 315360000}
Path(sys.argv[2]).write_text(json.dumps(data, indent=2) + "\n")
import re
chain = Path(sys.argv[4]).read_text()
blocks = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----\n?", chain, re.S)
app_leaf = data["bundle-info"]["distribution-certificate"].rstrip() + "\n"
Path(sys.argv[3]).write_text(app_leaf + blocks[1] + blocks[0])
print(sys.argv[2])
PY
java -jar "$sign_tool" sign-profile -mode localSign \
    -keyAlias "openharmony application profile release" -keyPwd 123456 -keystorePwd 123456 \
    -keystoreFile "$keystore" -signAlg SHA256withECDSA \
    -profileCertFile "$RDKHM_OH_SDK/toolchains/lib/OpenHarmonyProfileRelease.pem" \
    -inFile "$workspace/out/pintool-profile.json" \
    -outFile "$workspace/out/pintool-profile.p7b"
java -jar "$sign_tool" sign-app -mode localSign \
    -keyAlias "openharmony application release" -keyPwd 123456 -keystorePwd 123456 \
    -keystoreFile "$keystore" -signAlg SHA256withECDSA \
    -appCertFile "$workspace/out/pintool-app.pem" \
    -profileFile "$workspace/out/pintool-profile.p7b" \
    -inFile "$unsigned" -outFile "$output"
sha256sum "$output" | tee "$output.sha256"
echo "Built $output"
