#!/usr/bin/env python3
"""Follow upstream WorkDaddy releases and refresh PKGBUILD / .SRCINFO.

Only the "WorkDaddy" (cn profile) Linux DEBs are consumed. The other three
profiles (WorkDaddy-AI, CodeDaddy, CodeDaddy-CN) are deliberately ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO_API = "https://api.github.com/repos/babygoton/WorkDaddy/releases/latest"
DL_BASE = "https://github.com/babygoton/WorkDaddy/releases/download"
HEADERS = {
    "User-Agent": "workdaddy-aur-sync",
    "Accept": "application/vnd.github+json",
}
ASSETS = {
    "x86_64": "WorkDaddy_{v}_amd64.deb",
    "aarch64": "WorkDaddy_{v}_arm64.deb",
}


def fail(message: str) -> None:
    print(f"::error::{message}", flush=True)
    raise SystemExit(1)


def fetch(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    # lambda avoids interpreting backslashes in URLs/hashes as regex escapes
    result, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=re.M)
    if count != 1:
        fail(f"cannot rewrite {label}: regex matched {count} times (expected 1)")
    return result


def emit(values: dict[str, str]) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            for key, value in values.items():
                handle.write(f"{key}={value}\n")
    for key, value in values.items():
        print(f"  {key}={value}")


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--force", action="store_true",
                        help="re-apply the current upstream version (retry helper)")
    args = parser.parse_args()

    root = Path(args.repo_root)
    pb_path, si_path = root / "PKGBUILD", root / ".SRCINFO"
    pkgbuild, srcinfo = pb_path.read_text(), si_path.read_text()

    match = re.search(r"(?m)^pkgver=([^\s#]+)[ \t]*$", pkgbuild)
    if not match:
        fail("cannot read pkgver from PKGBUILD")
    current = match.group(1)

    try:
        release = json.loads(fetch(REPO_API))
    except Exception as exc:  # noqa: BLE001 - surfaced verbatim to the CI log
        fail(f"GitHub releases/latest unavailable: {exc}")

    if release.get("draft") or release.get("prerelease"):
        fail("latest release is a draft or prerelease; refusing to publish")
    version = str(release.get("tag_name", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        fail(f"unexpected tag_name: {version!r}")

    asset_names = {item.get("name", "") for item in release.get("assets", [])}
    for template in ASSETS.values():
        asset = template.format(v=version)
        if asset not in asset_names:
            fail(f"required asset {asset} missing from release {version}; "
                 "refusing a partial update")

    if not args.force and version_key(version) <= version_key(current):
        print(f"up to date: local={current} upstream={version}")
        emit({"changed": "false", "version": current})
        return

    digests = {
        item["name"]: item["digest"]
        for item in release.get("assets", [])
        if item.get("digest") and item.get("name")
    }
    local_dir = os.environ.get("WORKDADDY_DEB_DIR")
    sums: dict[str, str] = {}
    for arch, template in ASSETS.items():
        asset = template.format(v=version)
        if local_dir:
            data = (Path(local_dir) / asset).read_bytes()
        else:
            try:
                data = fetch(f"{DL_BASE}/{version}/{asset}", timeout=300)
            except Exception as exc:  # noqa: BLE001
                fail(f"download failed for {asset}: {exc}")
        sums[arch] = hashlib.sha256(data).hexdigest()
        api_digest = digests.get(asset, "").lower()
        if api_digest and api_digest != "sha256:" + sums[arch]:
            fail(f"GitHub asset digest disagrees with downloaded bytes for {asset}")
        print(f"{asset}: sha256={sums[arch]} ({len(data)} bytes)", flush=True)

    new_pb = pkgbuild
    # [ \t]*$ is deliberate: \s would swallow the following blank line.
    new_pb = sub_once(new_pb, r"(?m)^pkgver=\S+[ \t]*$", f"pkgver={version}",
                      "PKGBUILD pkgver")
    new_pb = sub_once(new_pb, r"(?m)^pkgrel=\d+[ \t]*$", "pkgrel=1",
                      "PKGBUILD pkgrel")
    new_pb = sub_once(new_pb, r"(?m)^sha256sums_x86_64=\('[0-9a-f]{64}'\)[ \t]*$",
                      f"sha256sums_x86_64=('{sums['x86_64']}')",
                      "PKGBUILD sha256sums_x86_64")
    new_pb = sub_once(new_pb, r"(?m)^sha256sums_aarch64=\('[0-9a-f]{64}'\)[ \t]*$",
                      f"sha256sums_aarch64=('{sums['aarch64']}')",
                      "PKGBUILD sha256sums_aarch64")

    new_si = srcinfo
    new_si = sub_once(new_si, r"(?m)^\tpkgver = .*$", f"\tpkgver = {version}",
                      ".SRCINFO pkgver")
    new_si = sub_once(new_si, r"(?m)^\tpkgrel = .*$", "\tpkgrel = 1",
                      ".SRCINFO pkgrel")
    for arch in ASSETS:
        asset = ASSETS[arch].format(v=version)
        key = f"source_{arch}"
        new_si = sub_once(new_si, rf"(?m)^\t{key} = .*$",
                          f"\t{key} = {asset}::{DL_BASE}/{version}/{asset}",
                          f".SRCINFO {key}")
    for arch in ASSETS:
        new_si = sub_once(new_si, rf"(?m)^\tsha256sums_{arch} = [0-9a-f]{{64}}$",
                          f"\tsha256sums_{arch} = {sums[arch]}",
                          f".SRCINFO sha256sums_{arch}")

    # All substitutions validated above; only now touch the files.
    pb_path.write_text(new_pb)
    si_path.write_text(new_si)

    print(f"updated {current} -> {version}", flush=True)
    emit({"changed": "true", "version": version})


if __name__ == "__main__":
    main()
