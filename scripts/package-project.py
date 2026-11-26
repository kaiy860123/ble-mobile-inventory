"""Create a deployable tarball with built UI, no experiments or credentials by default."""
import argparse
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--output",type=Path,default=ROOT/"deliverables/ble-mobile-inventory.tar.gz")
parser.add_argument("--include-device-credentials",action="store_true",help="Only for secure transfer to your own RPi, NEVER for a public release")
parser.add_argument("--wheelhouse",type=Path,help="Optional compatible Linux wheels, archived as wheelhouse/ for offline RPi installation")
args=parser.parse_args()
if not (ROOT/"web/dist/index.html").exists():raise SystemExit("Build the web UI first")
paths=[ROOT/p for p in ("pyproject.toml","README.md","GLOSSARY.md","src/ble_inventory","web/dist","firmware/src","firmware/platformio.ini","config/site.example.json","scripts","docs","infra")]
files=[]
for path in paths:
    files.extend([path] if path.is_file() else [p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts])
if args.include_device_credentials:
    for relative in ("config/private/site.cloud.json","config/private/device/private.key","config/private/device/certificate.pem","config/private/device/root-ca.pem"):
        path=ROOT/relative
        if not path.is_file():raise SystemExit(f"Missing {relative}")
        files.append(path)
args.output.parent.mkdir(parents=True,exist_ok=True)
with tarfile.open(args.output,"w:gz") as archive:
    for path in sorted(files):archive.add(path,arcname=path.relative_to(ROOT),recursive=False)
    if args.wheelhouse:
        wheels=sorted(args.wheelhouse.glob('*.whl'))
        if not wheels:raise SystemExit("No wheels in specified wheelhouse")
        for wheel in wheels:archive.add(wheel,arcname='wheelhouse/'+wheel.name,recursive=False)
print(f"Package: {args.output.name}; {len(files)} files; device credentials included: {args.include_device_credentials}")
