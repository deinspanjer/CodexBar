#!/usr/bin/env python3
"""Verify only the existing opt-in debug proof process; no desktop automation.

This is executable/build provenance, not proof of the requested two-row UI.
The proof entry point precedes settings construction and provider startup.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument("bundle", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
bundle = args.bundle.resolve()
executable = bundle / "Contents/MacOS/CodexBar"
with (bundle / "Contents/Info.plist").open("rb") as file:
    info = plistlib.load(file)
if info.get("CFBundleIdentifier") != "com.steipete.codexbar.debug":
    raise SystemExit("Only the debug bundle is accepted")
receipt = {
    "kind": "existing synthetic one-line proof process; not shipped-app scenario evidence",
    "bundle": str(bundle),
    "executable": str(executable),
    "executableSHA256": hashlib.sha256(executable.read_bytes()).hexdigest(),
    "CodexGitCommit": info.get("CodexGitCommit"),
    "CodexBuildTimestamp": info.get("CodexBuildTimestamp"),
    "CFBundleIdentifier": info.get("CFBundleIdentifier"),
    "arguments": [str(executable), "--menu-layout-proof"],
}
args.output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="codexbar-synthetic-process-") as scratch:
    scratch_path = Path(scratch)
    synthetic_home = scratch_path / "home"
    synthetic_home.mkdir()
    synthetic_tmp = scratch_path / "tmp"
    synthetic_tmp.mkdir()
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(synthetic_home),
        "CFFIXED_USER_HOME": str(synthetic_home),
        "XDG_CONFIG_HOME": str(synthetic_home / ".config"),
        "TMPDIR": str(synthetic_tmp) + "/",
        "CODEXBAR_DISABLE_KEYCHAIN_ACCESS": "1",
        "CODEXBAR_SUPPRESS_TEST_KEYCHAIN_ACCESS": "1",
        "CODEXBAR_TEST_CODEX_FILE_ISOLATION": "1",
        "CODEXBAR_TEST_SESSION_FILE_ISOLATION": "1",
        "SWIFT_TESTING": "1",
        "MallocLargeCache": "0",
    }
    with (args.output.parent / "synthetic-process.log").open("wb") as log:
        process = subprocess.Popen(receipt["arguments"], env=env, stdout=log, stderr=subprocess.STDOUT)
        receipt["ownedPID"] = process.pid
        try:
            time.sleep(3)
            receipt["aliveAfterSeconds"] = 3
            receipt["aliveAtVerification"] = process.poll() is None
            if process.poll() is None:
                libproc = ctypes.CDLL("/usr/lib/libproc.dylib")
                path_buffer = ctypes.create_string_buffer(4096)
                length = libproc.proc_pidpath(process.pid, path_buffer, len(path_buffer))
                receipt["runningExecutablePath"] = os.fsdecode(path_buffer.value) if length > 0 else None
                receipt["pathMatches"] = receipt["runningExecutablePath"] == str(executable)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            receipt["exitCodeAfterCleanup"] = process.returncode
            receipt["ownedProcessReaped"] = process.poll() is not None
args.output.write_text(json.dumps(receipt, indent=2) + "\n")
if not receipt.get("aliveAtVerification") or not receipt.get("pathMatches"):
    raise SystemExit("Synthetic process verification incomplete; inspect receipt/log")
print(json.dumps(receipt, indent=2))
