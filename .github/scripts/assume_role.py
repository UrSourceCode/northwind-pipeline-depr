import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


ROLE_ARN = os.environ.get("TENCENT_ROLE_ARN", "")
REGION = os.environ.get("TENCENT_REGION", "ap-singapore")
OIDC_PROVIDER = os.environ.get("OIDC_PROVIDER_NAME", "github-actions")

if not ROLE_ARN:
    print("[!] TENCENT_ROLE_ARN not set in repository secrets")
    sys.exit(1)

context = ssl.create_default_context()
token_url = (
    os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    + "&audience=sts.tencentcloudapi.com"
)
headers = {
    "Authorization": f"Bearer {os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}",
    "Accept": "application/json; api-version=2.0",
}

request = urllib.request.Request(token_url, headers=headers)
response = urllib.request.urlopen(request, context=context)
oidc_token = json.loads(response.read())["value"]
print("[+] Obtained GitHub OIDC token")

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

request = urllib.request.Request(sts_url, headers={"Host": "sts.tencentcloudapi.com"})

try:
    response = urllib.request.urlopen(request, context=context)
    data = json.loads(response.read().decode("utf-8"))
except Exception as error:
    print(f"[!] STS call failed: {error}")
    if isinstance(error, urllib.error.HTTPError):
        print(f"    Response body: {error.read().decode()}")
    sys.exit(1)

if "Error" in data.get("Response", {}):
    error = data["Response"]["Error"]
    print(f"[!] STS API error: {error.get('Code')} - {error.get('Message')}")
    sys.exit(1)

credentials = data["Response"]["Credentials"]
secret_id = credentials["TmpSecretId"]
secret_key = credentials["TmpSecretKey"]
token = credentials["Token"]

print("[+] Obtained temporary CAM credentials")
print(f"::add-mask::{secret_id}")
print(f"::add-mask::{secret_key}")
print(f"::add-mask::{token}")

credentials_file = os.path.join(
    os.environ.get("RUNNER_TEMP", "/tmp"), "pipeline.creds"
)
with open(credentials_file, "w", encoding="utf-8") as file:
    file.write(f"TENCENT_SECRET_ID={secret_id}\n")
    file.write(f"TENCENT_SECRET_KEY={secret_key}\n")
    file.write(f"TENCENT_TOKEN={token}\n")

print(f"[+] Credentials written to {credentials_file} (masked in logs)")
