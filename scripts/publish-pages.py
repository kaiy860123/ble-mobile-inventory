"""Configure this repository's Pages via an existing Git credential; never prints the token."""
import argparse
import json
import os
import re
import subprocess
import sys
from urllib.request import Request,urlopen
from urllib.error import HTTPError

parser=argparse.ArgumentParser()
parser.add_argument("--repository",default="kaiy860123/ble-mobile-inventory")
args=parser.parse_args()
if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",args.repository):parser.error("Invalid repository")
environment={**os.environ,"GIT_TERMINAL_PROMPT":"0","GCM_INTERACTIVE":"Never"}
credential=subprocess.run(["git","credential","fill"],input="protocol=https\nhost=github.com\n\n",text=True,capture_output=True,env=environment,timeout=30)
values=dict(line.split('=',1) for line in credential.stdout.splitlines() if '=' in line)
token=values.get('password')
if credential.returncode or not token:
    raise SystemExit("No existing noninteractive GitHub credential. Set Pages Source to GitHub Actions in repository Settings / Pages.")
url=f"https://api.github.com/repos/{args.repository}/pages"
def request(method,data=None):
    req=Request(url,data=json.dumps(data).encode() if data is not None else None,method=method,headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json"})
    with urlopen(req,timeout=30) as response:
        body=response.read()
        return json.loads(body) if body else {}
try:
    try:
        page=request('GET')
        if page.get('build_type')!='workflow':
            request('PUT',{'build_type':'workflow'})
            page=request('GET')
    except HTTPError as error:
        if error.code!=404:raise
        page=request('POST',{'build_type':'workflow'})
    print(json.dumps({"url":page.get('html_url'),"build_type":page.get('build_type'),"status":page.get('status')}))
except HTTPError as error:
    print(f"Pages configuration requires repository administration access (HTTP {error.code}). Configure Settings / Pages / GitHub Actions.",file=sys.stderr)
    raise SystemExit(2)
