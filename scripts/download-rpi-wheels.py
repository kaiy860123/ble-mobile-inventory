"""Prepare an ARM64 Linux wheelhouse on a faster host; no Windows-only dependencies."""
import argparse
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser()
parser.add_argument('--python-version',default='313',help='Target CPython tag, e.g. 313 for Python 3.13')
parser.add_argument('--output',type=Path,default=Path('deliverables/rpi-wheels'))
args=parser.parse_args()
if not args.python_version.isdigit():parser.error('Use a numeric CPython version tag')
args.output.mkdir(parents=True,exist_ok=True)
# Explicit Linux dependency closure avoids pip evaluating Windows host markers
# while downloading another platform's Bleak requirements.
requirements=['numpy>=2.1,<3','aiohttp>=3.11,<4','bleak>=1,<4','paho-mqtt>=2,<3',
              'aiohappyeyeballs>=2.5','aiosignal>=1.4','attrs>=17.3','frozenlist>=1.1',
              'multidict>=4,<8','propcache>=0.2','yarl>=1.17,<2','dbus-fast>=4',
              'idna>=2','typing_extensions>=4.7','setuptools>=75','wheel','packaging>=24']
command=[sys.executable,'-m','pip','download','--no-deps','--only-binary=:all:',
         '--platform','manylinux_2_28_aarch64','--platform','manylinux_2_27_aarch64','--platform','manylinux2014_aarch64',
         '--implementation','cp','--python-version',args.python_version,'--abi','cp'+args.python_version,'--abi','abi3','--abi','none',
         '--dest',str(args.output),'--timeout','120','--retries','5',*requirements]
subprocess.run(command,check=True)
print(f'ARM64 CPython {args.python_version} wheelhouse ready.')
