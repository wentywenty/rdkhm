# HAP signing policy

Effective 2026-11-19.

All HAPs that are built, staged under `out/haps`, or injected into an image must
be signed with the official OpenHarmony release key. Vendor CA, test keys and
`debugKey` are not used for integration artifacts.

## Official materials

| Item | Path / value |
| --- | --- |
| Keystore | `developtools/hapsigner/dist/OpenHarmony.p12` |
| Fallback keystore | `applications/standard/launcher/signature/OpenHarmony.p12` |
| Certificate chain | `developtools/hapsigner/dist/OpenHarmonyApplication.pem` |
| Fallback chain | `applications/standard/launcher/signature/OpenHarmonyApplication.cer` |
| Key alias | `openharmony application release` |
| Leaf certificate fingerprint (SHA-256) | `8E:93:86:3F:C3:2E:E2:38:06:0B:F6:9A:9B:37:E2:60:8F:FF:B2:1F:93:C8:62:DD:51:1C:BA:C9:F3:00:24:B5` |
| Sign tool | `prebuilts/ohos-sdk/linux/20/toolchains/lib/hap-sign-tool.jar` |

The `.pem`/`.cer` files are CA chains. The identity that devices and preinstall
allowlists use is the **leaf** certificate
`CN=OpenHarmony Application Release`. Its fingerprint above matches the
`app_signature` value used by `install_list_capability.json`.

Passwords and optional overrides come from `config/workspace.local.json`:

```
RDKHM_HAP_KEY_ALIAS              optional; default is the official alias
RDKHM_HAP_KEY_PWD                required
RDKHM_HAP_STORE_PWD              required
RDKHM_HAP_KEYSTORE               optional keystore override
RDKHM_HAP_CERT                   optional certificate-chain override
RDKHM_HAP_PROFILE                optional profile override
RDKHM_HAP_EXPECTED_FINGERPRINT   optional expected leaf fingerprint
RDKHM_HAP_SIGN_TOOL              optional sign-tool override
```

Do not commit private keys or passwords.

## Per-app profiles

A provision profile is bundle-specific. `scripts/build-hap.py` looks for
`*.p7b` under the app's `signature/`, `sign/` or `signs/` directory and prefers
`<app>.p7b`, then the first profile found. If no profile exists, the build
fails; it no longer emits an unsigned HAP silently.

Examples:

```
settings/signature/settings.p7b
contacts/sign/contacts.p7b
camera/signature/camera.p7b
systemui/signature/systemui.p7b
```

The official key is compatible with these existing profiles. The local
`OpenHarmony.p12` files shipped with some apps are **not** used for integration
artifacts.

## Build behaviour

```sh
./build hap settings
./build hap --all --force
```

- Every produced `out/haps/<app>.hap` is checked with `verify-app` and the
  signer certificate is compared with the official leaf fingerprint.
- If a HAP is already signed by the official key it is kept.
- If it is unsigned or signed by any other key it is re-signed with the
  official key.
- For Settings, `out/settings/Settings.hap` is staged from the same signed
  artifact.
- `--no-sign` is for debugging only and prints a warning. Never inject an
  unsigned HAP into an image.

Existing HAPs under `out/haps` that predate this policy must be rebuilt or
re-signed before use:

```sh
./build hap --all --force
```

## Verify

```sh
python3 scripts/check-hap-signatures.py
python3 scripts/check-hap-signatures.py out/haps/settings.hap out/settings/Settings.hap
```

The checker runs `hap-sign-tool verify-app`, extracts the signing chain and
compares the leaf SHA-256 fingerprint with the official reference. The reference
is read from a prebuilt official HAP (`applications/standard/hap/Launcher.hap`,
then `SystemUI.hap`, `Settings.hap`), with
`RDKHM_HAP_EXPECTED_FINGERPRINT` and a built-in constant as fallbacks.

`verify-openharmony-image.py` runs the same check when the rebuilt Settings HAP
is injected.

## Image injection

The authoritative injection list is the `image` section of
`config/build/haps.json`; `scripts/image_haps.py` resolves it and both
`make-openharmony-image.sh` and `verify-openharmony-image.py` consume it.
A HAP injected into the image must satisfy one of:

- signed by the official OpenHarmony release key, or
- match the `app_signature` bound to its bundle in
  `overlay/vendor/drobotics/rdk_x5/preinstall-config/install_list_capability.json`
  or `install_list_permissions.json`.

The second branch exists for upstream system apps whose privileged capability
grants are tied to the preinstall fingerprint (currently contacts, mms, callui,
filepicker and camera). Re-signing one of these with the official key requires
updating the allowlist entries in the same change, otherwise the app loses its
preinstall capabilities.

```sh
python3 scripts/image_haps.py --check
python3 scripts/check-hap-signatures.py --accept-allowlist $(python3 scripts/image_haps.py --tsv | cut -f1)
```

`--accept-allowlist` is only used for image staging. Running the checker
without it still enforces the official key alone.

## Consequences

- `install_list_capability.json` `app_signature` entries must reference the
  official leaf fingerprint. Mixing vendor CA, test-key and official signatures
  can cause `install sign info inconsistent` or preinstall rejection.
- HAPs built before 2026-11-19 may still carry vendor CA signatures. The
  signature checker reports them as failures until rebuilt.
- The official key in the source tree is a development key. Production images
  should use the vendor/CA key set and matching profiles.
