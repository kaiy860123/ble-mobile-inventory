"""AWS bootstrap with a strict Free Plan preflight. Never prints or publishes credentials."""
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import urlopen
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "config/private/aws-deployment.json"


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def private_write(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)


def preflight(session):
    if session.get_credentials() is None:
        raise RuntimeError("No local AWS credentials. Use AWS CloudShell or configure an AWS profile; never paste keys into chat.")
    account = session.client("sts").get_caller_identity()
    plan = session.client("freetier", region_name="us-east-1").get_account_plan_state()
    if plan.get("accountPlanType") != "FREE" or plan.get("accountPlanStatus") != "ACTIVE":
        raise RuntimeError("Zero-cost policy: deployment requires an ACTIVE FREE account plan; no paid upgrade is performed.")
    expiration = plan.get("accountPlanExpirationDate")
    if expiration and expiration <= datetime.now(timezone.utc):
        raise RuntimeError("Free plan has expired")
    print(json.dumps({"account_suffix":account["Account"][-4:], "plan":plan["accountPlanType"], "status":plan["accountPlanStatus"],
                      "expiration":expiration, "remaining_credits":plan.get("accountPlanRemainingCredits")}, default=str))
    return plan


def deploy(session, args):
    preflight(session)
    if STATE.exists():
        old_state=json.loads(STATE.read_text(encoding="utf-8"))
        if old_state.get("stack")!=args.stack or old_state.get("region")!=args.region:
            raise RuntimeError("Existing deployment state belongs to a different stack or region")
    cfn = session.client("cloudformation")
    template = (ROOT / "infra/aws/template.json").read_text(encoding="utf-8")
    cfn.validate_template(TemplateBody=template)
    parameters=[{"ParameterKey":"SiteId","ParameterValue":args.site}, {"ParameterKey":"DeviceClientId","ParameterValue":"rpi-"+args.site}]
    request=dict(StackName=args.stack, TemplateBody=template, Parameters=parameters, Capabilities=["CAPABILITY_IAM"],Tags=[{"Key":"Project","Value":"ble-mobile-inventory"}])
    try:
        existing=cfn.describe_stacks(StackName=args.stack)["Stacks"][0]
    except ClientError as error:
        if "does not exist" not in str(error):
            raise
        existing=None
    if existing:
        if not any(tag["Key"]=="Project" and tag["Value"]=="ble-mobile-inventory" for tag in existing.get("Tags",[])):
            raise RuntimeError("Refusing to modify a stack without the project tag")
        try:
            cfn.update_stack(**request)
            cfn.get_waiter("stack_update_complete").wait(StackName=args.stack,WaiterConfig={"Delay":5,"MaxAttempts":180})
        except ClientError as error:
            if "No updates are to be performed" not in str(error):
                raise
    else:
        cfn.create_stack(**request)
        print("Creating project stack; waiting for CloudFormation...")
        cfn.get_waiter("stack_create_complete").wait(StackName=args.stack,WaiterConfig={"Delay":5,"MaxAttempts":180})
    stack=cfn.describe_stacks(StackName=args.stack)["Stacks"][0]
    outputs={o["OutputKey"]:o["OutputValue"] for o in stack["Outputs"]}
    outputs.update(region=args.region,stack=args.stack)
    iot=session.client("iot")
    outputs["endpoint"]=iot.describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]
    if STATE.exists():
        old=json.loads(STATE.read_text(encoding="utf-8"))
        if old.get("stack")!=args.stack or old.get("region")!=args.region:
            raise RuntimeError("Existing deployment state belongs to a different stack or region")
        outputs.update({k:v for k,v in old.items() if k in ("certificateId","certificateArn")})
    save_json(STATE,outputs)
    public={"region":args.region,"endpoint":outputs["endpoint"],"userPoolId":outputs["UserPoolId"],"userPoolClientId":outputs["UserPoolClientId"],"identityPoolId":outputs["IdentityPoolId"],"topic":outputs["Topic"]}
    save_json(ROOT / "web/public/cloud-config.json",public)
    print("Stack ready. Public connection settings written; no private keys included.")


def device(session,args):
    preflight(session)
    state=json.loads(STATE.read_text(encoding="utf-8"))
    folder=ROOT/"config/private/device"
    folder.mkdir(parents=True,exist_ok=True)
    key=folder/"private.key"
    if state["region"]!=args.region:
        raise RuntimeError("Use the region recorded in the deployment state")
    iot=session.client("iot")
    if not state.get("certificateId"):
        if key.exists():
            raise RuntimeError("A private key exists without matching deployment state; refusing to overwrite")
        certificate=iot.create_keys_and_certificate(setAsActive=True)
        state.update(certificateId=certificate["certificateId"],certificateArn=certificate["certificateArn"])
        save_json(STATE,state)
        # Write immediately; never render returned private key or certificate data.
        private_write(key,certificate["keyPair"]["PrivateKey"])
        private_write(folder/"certificate.pem",certificate["certificatePem"])
    elif not key.is_file() or not (folder/"certificate.pem").is_file():
        raise RuntimeError("Incomplete local credential files; explicit recovery required, no automatic rotation")
    iot.attach_policy(policyName=state["DevicePolicyName"],target=state["certificateArn"])
    iot.attach_thing_principal(thingName=state["ThingName"],principal=state["certificateArn"])
    if not (folder/"root-ca.pem").exists():
        with urlopen("https://www.amazontrust.com/repository/AmazonRootCA1.pem",timeout=30) as response:
            private_write(folder/"root-ca.pem",response.read().decode("ascii"))
    config=json.loads((ROOT/args.config).read_text(encoding="utf-8"))
    config["cloud"]={"enabled":True,"endpoint":state["endpoint"],"region":state["region"],"topic":state["Topic"],"client_id":state["ClientId"],"cert_path":"config/private/device/certificate.pem","key_path":"config/private/device/private.key","ca_path":"config/private/device/root-ca.pem"}
    save_json(ROOT/"config/private/site.cloud.json",config)
    print("Device credential saved under config/private/device; copy securely to the RPi. No credential contents printed.")


def viewer(session,args):
    preflight(session)
    state=json.loads(STATE.read_text(encoding="utf-8"))
    if state["region"]!=args.region:
        raise RuntimeError("Use the region recorded in the deployment state")
    auth=session.client("cognito-idp");identity=session.client("cognito-identity")
    email=args.email or input("Viewer email (no email will be sent): ").strip()
    password=getpass.getpass("Viewer password (12+ characters, not displayed): ")
    try:
        auth.admin_create_user(UserPoolId=state["UserPoolId"],Username=email,UserAttributes=[{"Name":"email","Value":email},{"Name":"email_verified","Value":"true"}],MessageAction="SUPPRESS")
        auth.admin_set_user_password(UserPoolId=state["UserPoolId"],Username=email,Password=password,Permanent=True)
    except auth.exceptions.UsernameExistsException:
        print("Existing viewer: validating supplied password; not changing it.")
    result=auth.admin_initiate_auth(UserPoolId=state["UserPoolId"],ClientId=state["UserPoolClientId"],AuthFlow="ADMIN_USER_PASSWORD_AUTH",AuthParameters={"USERNAME":email,"PASSWORD":password})
    del password
    token=result["AuthenticationResult"]["IdToken"]
    provider=f"cognito-idp.{state['region']}.amazonaws.com/{state['UserPoolId']}"
    identity_id=identity.get_id(IdentityPoolId=state["IdentityPoolId"],Logins={provider:token})["IdentityId"]
    session.client("iot").attach_policy(policyName=state["ViewerPolicyName"],target=identity_id)
    print("Viewer enrolled with read-only topic access; no invitation email sent.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["preflight","deploy","device","viewer"])
    parser.add_argument("--profile")
    parser.add_argument("--region",default="ap-northeast-1")
    parser.add_argument("--stack",default="ble-mobile-inventory")
    parser.add_argument("--site",default="indoor-demo")
    parser.add_argument("--config",default="config/site.example.json")
    parser.add_argument("--email")
    args=parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,40}",args.site) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]{0,60}",args.stack):
        parser.error("Invalid project stack/site name")
    session=boto3.Session(profile_name=args.profile,region_name=args.region)
    try:
        {"preflight":lambda s,a:preflight(s),"deploy":deploy,"device":device,"viewer":viewer}[args.command](session,args)
    except (RuntimeError,ClientError,NoCredentialsError,FileNotFoundError) as error:
        # ClientError messages contain operational errors, never API response credential payloads.
        print(f"AWS setup stopped: {error}",file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
