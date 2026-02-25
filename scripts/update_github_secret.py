#!/usr/bin/env python3
"""
Update a GitHub Actions secret with a new value via the GitHub REST API.
Uses a PAT (Personal Access Token) from the GITHUB_TOKEN environment variable.

Usage:
    GITHUB_TOKEN='ghp_xxx' python3 scripts/update_github_secret.py \
        --repo owner/repo --secret TOKEN_JSON --value '{"token": ...}'
"""
import os
import sys
import json
import base64
import argparse
import requests
from nacl import encoding, public


def encrypt_secret(public_key_value: str, secret_value: str) -> str:
    """Encrypt a secret using the repo's public key for GitHub Secrets."""
    public_key_bytes = base64.b64decode(public_key_value)
    sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def update_secret(repo: str, secret_name: str, secret_value: str, token: str) -> bool:
    """Update a GitHub Actions secret via the REST API."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Step 1: Get the repo's public key
    pk_url = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
    pk_resp = requests.get(pk_url, headers=headers)
    if pk_resp.status_code != 200:
        print(f"❌ Failed to get public key: {pk_resp.status_code} {pk_resp.text}")
        return False

    pk_data = pk_resp.json()
    key_id = pk_data["key_id"]
    key_value = pk_data["key"]

    # Step 2: Encrypt the secret
    encrypted_value = encrypt_secret(key_value, secret_value)

    # Step 3: PUT the secret
    put_url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
    payload = {"encrypted_value": encrypted_value, "key_id": key_id}
    put_resp = requests.put(put_url, headers=headers, json=payload)
    if put_resp.status_code in (201, 204):
        print(f"✅ Successfully updated secret '{secret_name}' in {repo}")
        return True
    else:
        print(f"❌ Failed to update secret: {put_resp.status_code} {put_resp.text}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--secret", required=True, help="Secret name")
    parser.add_argument("--value", help="Secret value (JSON string)")
    parser.add_argument("--file", help="Path to file whose contents become the secret value")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("❌ Set GITHUB_TOKEN env var to a Personal Access Token with 'secrets' scope.")
        sys.exit(1)

    if args.file:
        with open(args.file, "r") as f:
            value = f.read().strip()
    elif args.value:
        value = args.value
    else:
        print("❌ Either --value or --file is required.")
        sys.exit(1)

    success = update_secret(args.repo, args.secret, value, token)
    sys.exit(0 if success else 1)
