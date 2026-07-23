"""
Exchange a GitHub Actions OIDC token for Tencent Cloud CAM
temporary credentials via STS AssumeRoleWithWebIdentity.

Writes credentials to $RUNNER_TEMP/pipeline.creds for later sourcing.
"""
import os
import json
import time
import random
import urllib.request
import urllib.parse
import ssl

ROLE_ARN = os.environ.get("TENCENT_ROLE_ARN", "")
REGION   = os.environ.get("TENCENT_REGION", "ap-singapore")
OIDC_PROVIDER = os.environ.get("OIDC_PROVIDER_NAME", "github-actions")

if not ROLE_ARN:
    print("[!] TENCENT_ROLE_ARN not set in repository secrets")
    exit(1)

ctx = ssl.create_default_context()

# ── Step 1: request OIDC token from GitHub ──
token_url = (
    os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    + "&audience=sts.tencentcloudapi.com"
)
headers = {
    "Authorization": f"Bearer {os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}",
    "Accept": "application/json; api-version=2.0",
}

req = urllib.request.Request(token_url, headers=headers)
resp = urllib.request.urlopen(req, context=ctx)
oidc_token = json.loads(resp.read())["value"]
print("[+] Obtained GitHub OIDC token")

# ── Step 2: call STS AssumeRoleWithWebIdentity ──
params = urllib.parse.urlencode({
    "Action": "AssumeRoleWithWebIdentity",
    "Version": "2018-08-13",
    "Region": REGION,
    "Timestamp": str(int(time.time())),
    "Nonce": str(random.randint(10000, 99999)),
    "ProviderId": OIDC_PROVIDER,
    "RoleArn": ROLE_ARN,
    "WebIdentityToken": oidc_token,
    "RoleSessionName": "gh-actions-pipeline",
    "DurationSeconds": 3600,
})
sts_url = f"https://sts.tencentcloudapi.com/?{params}"

req = urllib.request.Request(sts_url)
req.add_header("Host", "sts.tencentcloudapi.com")

try:
    resp = urllib.request.urlopen(req, context=ctx)
    raw = resp.read().decode("utf-8")
    data = json.loads(raw)
except Exception as e:
    print(f"[!] STS call failed: {e}")
    if isinstance(e, urllib.error.HTTPError):
        print(f"    Response body: {e.read().decode()}")
    exit(1)

if "Error" in data.get("Response", {}):
    err = data["Response"]["Error"]
    print(f"[!] STS API error: {err.get('Code')} - {err.get('Message')}")
    exit(1)

creds = data["Response"]["Credentials"]
print("[+] Obtained temporary CAM credentials")

# ── Step 3: write to a temp file (NOT $GITHUB_ENV — avoids env-block leak) ──
creds_file = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "pipeline.creds")
with open(creds_file, "w") as f:
    f.write(f'TENCENT_SECRET_ID={creds["TmpSecretId"]}\n')
    f.write(f'TENCENT_SECRET_KEY={creds["TmpSecretKey"]}\n')
    f.write(f'TENCENT_TOKEN={creds["Token"]}\n')

print(f"[+] Credentials written to {creds_file}")
