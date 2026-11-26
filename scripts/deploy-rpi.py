"""Deploy via SSH key or a hidden password prompt; never stores credentials."""
import argparse
import getpass
import hashlib
import hmac
from pathlib import Path
import re
import subprocess
import sys
import time

parser=argparse.ArgumentParser()
parser.add_argument("host")
parser.add_argument("--user",required=True)
parser.add_argument("--archive",type=Path,default=Path("deliverables/ble-mobile-inventory.tar.gz"))
parser.add_argument("--install-service",action="store_true")
parser.add_argument("--password-auth",action="store_true",help="Use a hidden prompt; password is never a command argument or saved")
args=parser.parse_args()
if not re.fullmatch(r"[A-Za-z0-9.-]+",args.host) or not re.fullmatch(r"[a-z_][a-z0-9_-]*",args.user):parser.error("Invalid SSH host/user")
if not args.archive.is_file():parser.error("Build the deployment archive first")
target=f"{args.user}@{args.host}"


def password_deploy():
    import paramiko
    password=getpass.getpass("SSH password (not stored): ")
    client=paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(args.host,port=22,username=args.user,password=password,look_for_keys=False,allow_agent=False,timeout=15,auth_timeout=20)
        def run(command,input_text=None,timeout_s=1800):
            channel=client.get_transport().open_session()
            channel.exec_command(command)
            if input_text is not None:
                channel.sendall(input_text.encode('utf-8'))
            channel.shutdown_write()
            started=time.monotonic()
            while True:
                for ready,receive,output in ((channel.recv_ready,channel.recv,sys.stdout),(channel.recv_stderr_ready,channel.recv_stderr,sys.stderr)):
                    if ready():
                        output.write(receive(32768).decode('utf-8',errors='replace'));output.flush()
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():break
                if time.monotonic()-started>timeout_s:
                    channel.close();raise RuntimeError('Remote command timed out')
                time.sleep(.1)
            status=channel.recv_exit_status()
            if status:raise RuntimeError(f'Remote command failed with exit status {status}')
        print('SSH host key verified. Preparing project directory.',flush=True)
        run('mkdir -p ~/ble-mobile-inventory')
        with client.open_sftp() as sftp:
            remote_home=sftp.normalize('.')
            remote_archive=remote_home+'/ble-mobile-inventory/deploy.tar.gz'
            sftp.put(str(args.archive.resolve()),remote_archive)
        # Hash on the RPi rather than downloading a large wheelhouse back to verify it.
        _,checksum_output,checksum_error=client.exec_command('sha256sum ~/ble-mobile-inventory/deploy.tar.gz',timeout=60)
        digest_fields=checksum_output.read().decode('ascii',errors='replace').split()
        checksum_status=checksum_output.channel.recv_exit_status()
        remote_digest=digest_fields[0] if digest_fields else ''
        if checksum_status or not re.fullmatch(r'[0-9a-f]{64}',remote_digest):
            raise RuntimeError('Could not verify remote archive checksum')
        local_hash=hashlib.sha256(args.archive.read_bytes()).hexdigest()
        if not hmac.compare_digest(local_hash,remote_digest):raise RuntimeError('Uploaded archive checksum mismatch')
        print('Deployment archive checksum verified.',flush=True)
        run('cd ~/ble-mobile-inventory && tar xzf deploy.tar.gz && bash scripts/setup-rpi.sh')
        if args.install_service:
            sudo_password=getpass.getpass('sudo password (Enter = SSH password, not stored): ') or password
            run("cd ~/ble-mobile-inventory && sudo -S -p '' bash scripts/install-service.sh",sudo_password+'\n')
            del sudo_password
        run("cd ~/ble-mobile-inventory && .venv/bin/python -c 'import ble_inventory; print(ble_inventory.__version__)'")
        print('RPi deployment complete.',flush=True)
    finally:
        client.close()
        del password


if args.password_auth:
    password_deploy()
else:
    subprocess.run(["ssh",target,"mkdir -p ~/ble-mobile-inventory"],check=True)
    subprocess.run(["scp",str(args.archive.resolve()),target+":ble-mobile-inventory/deploy.tar.gz"],check=True)
    subprocess.run(["ssh",target,"cd ~/ble-mobile-inventory && tar xzf deploy.tar.gz && bash scripts/setup-rpi.sh"],check=True)
    if args.install_service:subprocess.run(["ssh","-t",target,"cd ~/ble-mobile-inventory && sudo bash scripts/install-service.sh"],check=True)
