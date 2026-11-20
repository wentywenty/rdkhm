#!/usr/bin/env python3
"""Expose the pinned OpenHarmony SDK in the layout expected by hvigor 6.x."""
import json
from pathlib import Path


def ensure_sdk_home(root, sdk):
    """Return an SDK root with the newer ``default/openharmony`` layout.

    The OpenHarmony 6.0 SDK ships the legacy ``ets/``, ``toolchains/`` layout.
    Current hvigor rejects it in place, so expose the same bytes through the
    newer layout under ``out/``. Nothing is copied.
    """
    sdk = Path(sdk)
    if (sdk / "default/openharmony").is_dir():
        return sdk
    if not (sdk / "toolchains/oh-uni-package.json").is_file():
        raise RuntimeError(f"Not an OpenHarmony SDK: {sdk}")
    package = json.loads((sdk / "toolchains/oh-uni-package.json").read_text())
    api = str(package.get("apiVersion") or sdk.name)
    version = str(package.get("version") or package.get("platformVersion") or api)
    home = Path(root) / "out/sdk" / f"openharmony-{api}"
    target = home / "default/openharmony"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("ets", "js", "native", "previewer", "toolchains"):
        source = sdk / name
        link = target / name
        if not source.is_dir():
            raise RuntimeError(f"SDK component is missing: {source}")
        if link.is_symlink():
            if link.resolve() == source.resolve():
                continue
            link.unlink()
        elif link.exists():
            raise RuntimeError(f"Unexpected non-symlink SDK component: {link}")
        link.symlink_to(source, target_is_directory=True)
    metadata = {
        "meta": {"version": "1.0.0"},
        "data": {
            "apiVersion": api,
            "displayName": f"OpenHarmony {version}",
            "path": f"OpenHarmony-{version}",
            "platformVersion": version,
            "releaseType": package.get("releaseType", "Beta1"),
            "version": version,
            "stage": package.get("stage", "Beta1"),
        },
    }
    (home / "default/sdk-pkg.json").write_text(json.dumps(metadata, indent=2) + "\n")
    version_link = home / api
    if version_link.is_symlink() or version_link.exists():
        if version_link.resolve() != (home / "default/openharmony").resolve():
            version_link.unlink()
    if not version_link.exists():
        version_link.symlink_to(Path("default/openharmony"), target_is_directory=True)
    return home
