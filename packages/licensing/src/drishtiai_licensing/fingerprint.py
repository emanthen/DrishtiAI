"""
Hardware fingerprint — binds a license to a specific machine.

Collects 4 stable identifiers (motherboard serial, CPU ID, primary disk serial,
primary NIC MAC). Verification uses a quorum (default 3-of-4) so a single
component swap (NIC card, extra disk) doesn't lock out a legitimate install,
while a full copy to different hardware fails.
"""
from __future__ import annotations

import hashlib
import platform
import re
import subprocess
from dataclasses import asdict, dataclass


@dataclass
class FingerprintBundle:
    motherboard: str
    cpu: str
    disk: str
    mac: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FingerprintBundle":
        return cls(
            motherboard=str(d.get("motherboard", "unknown")),
            cpu=str(d.get("cpu", "unknown")),
            disk=str(d.get("disk", "unknown")),
            mac=str(d.get("mac", "unknown")),
        )


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=5).decode().strip()
    except Exception:
        return ""


def _norm(s: str) -> str:
    """Strip non-alphanumeric, uppercase, cap at 64 chars."""
    return re.sub(r"[^a-zA-Z0-9]", "", s).upper()[:64] or "unknown"


def _get_motherboard() -> str:
    if platform.system() == "Windows":
        out = _run(["wmic", "baseboard", "get", "SerialNumber"])
        lines = [l.strip() for l in out.splitlines() if l.strip() and "SerialNumber" not in l]
        return _norm(lines[0]) if lines else "unknown"
    out = _run(["dmidecode", "-s", "baseboard-serial-number"])
    if out and "Not Specified" not in out and out not in ("None", ""):
        return _norm(out)
    try:
        with open("/sys/class/dmi/id/board_serial") as f:
            return _norm(f.read())
    except OSError:
        return "unknown"


def _get_cpu() -> str:
    if platform.system() == "Windows":
        out = _run(["wmic", "cpu", "get", "ProcessorId"])
        lines = [l.strip() for l in out.splitlines() if l.strip() and "ProcessorId" not in l]
        return _norm(lines[0]) if lines else "unknown"
    out = _run(["dmidecode", "-s", "processor-serial-number"])
    if out and "Not Specified" not in out and out not in ("None", ""):
        return _norm(out)
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    return _norm(line.split(":", 1)[-1])
    except OSError:
        pass
    return "unknown"


def _get_disk() -> str:
    if platform.system() == "Windows":
        out = _run(["wmic", "diskdrive", "get", "SerialNumber"])
        lines = [l.strip() for l in out.splitlines() if l.strip() and "SerialNumber" not in l]
        return _norm(lines[0]) if lines else "unknown"
    for dev in ("/dev/sda", "/dev/nvme0n1", "/dev/vda"):
        out = _run(["lsblk", "--nodeps", "-no", "SERIAL", dev])
        if out:
            return _norm(out)
    out = _run(["hdparm", "-I", "/dev/sda"])
    m = re.search(r"Serial Number:\s+(\S+)", out)
    if m:
        return _norm(m.group(1))
    return "unknown"


def _get_mac() -> str:
    if platform.system() == "Windows":
        out = _run(["getmac", "/fo", "csv", "/nh"])
        parts = out.split(",")
        return _norm(parts[0].strip('"')) if parts else "unknown"
    out = _run(["ip", "link", "show"])
    macs = re.findall(r"link/ether\s+([0-9a-f:]{17})", out)
    if macs:
        return _norm(macs[0])
    try:
        import os
        for iface in sorted(os.listdir("/sys/class/net")):
            try:
                with open(f"/sys/class/net/{iface}/address") as f:
                    addr = f.read().strip()
                if addr and addr != "00:00:00:00:00:00":
                    return _norm(addr)
            except OSError:
                continue
    except OSError:
        pass
    return "unknown"


def generate_fingerprint() -> FingerprintBundle:
    """Collect stable hardware identifiers from the current machine."""
    return FingerprintBundle(
        motherboard=_get_motherboard(),
        cpu=_get_cpu(),
        disk=_get_disk(),
        mac=_get_mac(),
    )


def fingerprint_digest(bundle: FingerprintBundle) -> str:
    """SHA-256 of all four identifiers — compact single-string identifier."""
    raw = "|".join([bundle.motherboard, bundle.cpu, bundle.disk, bundle.mac])
    return hashlib.sha256(raw.encode()).hexdigest()


def matches(bundle: FingerprintBundle, current: FingerprintBundle, quorum: int = 3) -> bool:
    """Return True if at least `quorum` of the 4 identifiers match."""
    score = sum([
        bundle.motherboard == current.motherboard,
        bundle.cpu == current.cpu,
        bundle.disk == current.disk,
        bundle.mac == current.mac,
    ])
    return score >= quorum
