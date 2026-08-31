#!/usr/bin/env python3
"""Verify one role-aware Hymn Letter Drive delivery receipt against its manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class DeliverySetError(ValueError):
    pass


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(item: dict, receipt: bool = False) -> tuple:
    return (
        str(item.get("episode_id", "")),
        str(item.get("role", "")),
        str(item.get("name" if receipt else "target_name", "")),
        item.get("size"),
        str(item.get("sha256", "")),
    )


def verify(manifest_path: Path, receipt_path: Path) -> dict:
    manifest = load_json(manifest_path)
    receipt = load_json(receipt_path)
    if manifest.get("execution_authorized") is not True:
        raise DeliverySetError("manifest is not execution-authorized")
    payloads = manifest.get("payloads")
    delivered = receipt.get("payloads")
    if not isinstance(payloads, list) or not payloads:
        raise DeliverySetError("manifest payloads are missing")
    if not isinstance(delivered, list):
        raise DeliverySetError("receipt payloads are missing")
    expected = [identity(item) for item in payloads]
    actual = [identity(item, receipt=True) for item in delivered]
    if len(expected) != len(set(expected)):
        raise DeliverySetError("manifest contains duplicate delivery identities")
    if set(actual) != set(expected) or len(actual) != len(expected):
        raise DeliverySetError("receipt does not contain the exact manifest payload set")

    required_roles = manifest.get("required_roles", {})
    for episode_id, roles in required_roles.items():
        present = {
            item.get("role")
            for item in payloads
            if str(item.get("episode_id")) == str(episode_id)
        }
        if set(roles) != present:
            raise DeliverySetError(f"episode {episode_id} required role set mismatch")

    if receipt.get("manifest_sha256") != sha256_file(manifest_path):
        raise DeliverySetError("receipt is not bound to the current manifest hash")
    target = manifest.get("target", {})
    new_folder = receipt.get("new_folder", {})
    if new_folder.get("name") != target.get("folder_name"):
        raise DeliverySetError("receipt folder name differs from manifest target")
    if new_folder.get("file_count") != len(payloads):
        raise DeliverySetError("receipt file count differs from manifest payload count")
    folder_id = str(new_folder.get("remote_id", ""))
    if not folder_id or folder_id.startswith("local-"):
        raise DeliverySetError("receipt has no synced remote folder ID")
    for item in delivered:
        remote_id = str(item.get("remote_id", ""))
        if not remote_id or remote_id.startswith("local-"):
            raise DeliverySetError(f"payload has no synced remote ID: {item.get('name')}")

    required_checks = {
        "source_manifest_valid",
        "drivefs_readback_sha256_all_match",
        "remote_ids_all_nonlocal",
        "remote_sizes_all_match",
        "new_folder_exact_payload_set",
    }
    verification = receipt.get("verification", {})
    failed = sorted(key for key in required_checks if verification.get(key) is not True)
    if not (
        verification.get("parent_contains_target_folder_exactly_once") is True
        or verification.get("parent_contains_only_new_folder") is True
    ):
        failed.append("parent_contains_target_folder_exactly_once")
    if failed:
        raise DeliverySetError("receipt verification failed or missing: " + ", ".join(failed))
    if not (
        verification.get("old_remote_ids_trashed_or_tombstoned") is True
        or verification.get("superseded_payloads_replaced_exactly") is True
    ):
        raise DeliverySetError(
            "receipt proves neither stale-ID cleanup nor exact superseded-payload replacement"
        )
    return {
        "status": "PASS",
        "folder_name": new_folder["name"],
        "folder_remote_id": folder_id,
        "payload_count": len(payloads),
        "episodes": sorted(required_roles),
        "roles": required_roles,
        "manifest_sha256": receipt["manifest_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.manifest, args.receipt)
    except (DeliverySetError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
