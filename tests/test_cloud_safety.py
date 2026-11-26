import importlib.util
import json
from pathlib import Path
import pytest


def provision_module():
    path=Path('scripts/aws-provision.py')
    spec=importlib.util.spec_from_file_location('aws_provision',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_deployment_refuses_paid_plan():
    module=provision_module()
    class Client:
        def get_caller_identity(self):return {'Account':'123456789012'}
        def get_account_plan_state(self):return {'accountPlanType':'PAID','accountPlanStatus':'ACTIVE'}
    class Session:
        def get_credentials(self):return object()
        def client(self,*args,**kwargs):return Client()
    with pytest.raises(RuntimeError,match='ACTIVE FREE'):module.preflight(Session())


def test_no_browser_publish_or_guest_policy():
    template=json.loads(Path('infra/aws/template.json').read_text(encoding='utf-8'))
    resources=template['Resources']
    assert resources['IdentityPool']['Properties']['AllowUnauthenticatedIdentities'] is False
    for name in ('ViewerRole','ViewerIoTPolicy'):
        value=json.dumps(resources[name])
        assert 'iot:Publish' not in value and 'iot:AttachPolicy' not in value and 'iot:*' not in value
    assert resources['UserPool']['Properties']['AdminCreateUserConfig']['AllowAdminCreateUserOnly'] is True
