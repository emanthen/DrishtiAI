"""
DrishtiAI License CLI — Prabhat's operator tool for issuing and managing licenses.

Usage:
  python cli.py issue   --client "Everest Mall" --site SITE-001 --days 365 \
                        --cameras 8 --plan mid --private-key /secure/private_key.pem
  python cli.py inspect /path/to/license.token
  python cli.py list
  python cli.py revoke  LIC-XXXX-XXXX

The SQLite database lives at ~/.drishtiai/licenses.db and is the source of truth
for billing and invoice status. It never leaves this machine.

SECURITY: The Ed25519 private key must NEVER be committed to version control.
Store it only on your secure offline machine or license server.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

from drishtiai_licensing.fingerprint import FingerprintBundle
from drishtiai_licensing.token import LicenseClaims, PlanTier, sign, verify

_DB_PATH = Path(os.getenv("DRISHTI_LICENSE_DB", Path.home() / ".drishtiai" / "licenses.db"))

_DEFAULT_FEATURES = {
    PlanTier.smb: ["anpr", "gate_automation", "alerts", "parking"],
    PlanTier.mid: ["anpr", "gate_automation", "alerts", "parking", "analytics", "reports", "webhooks"],
    PlanTier.enterprise: [
        "anpr", "gate_automation", "alerts", "parking", "analytics", "reports",
        "webhooks", "visitor_passes", "api_access", "custom_retention",
    ],
}

_DEFAULT_CAMERAS = {PlanTier.smb: 4, PlanTier.mid: 16, PlanTier.enterprise: 64}


def _db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            license_id   TEXT PRIMARY KEY,
            client_name  TEXT NOT NULL,
            site_id      TEXT NOT NULL,
            plan_tier    TEXT NOT NULL,
            camera_limit INTEGER NOT NULL,
            issued_at    TEXT NOT NULL,
            expires_at   TEXT NOT NULL,
            grace_days   INTEGER NOT NULL DEFAULT 14,
            revoked      INTEGER NOT NULL DEFAULT 0,
            invoice_ref  TEXT,
            notes        TEXT,
            token_path   TEXT
        )
    """)
    conn.commit()
    return conn


def _parse_fingerprint(mb: str, cpu: str, disk: str, mac: str) -> FingerprintBundle:
    return FingerprintBundle(motherboard=mb, cpu=cpu, disk=disk, mac=mac)


@click.group()
def cli():
    """DrishtiAI license management."""


@cli.command()
@click.option("--client", required=True, help="Client/company name")
@click.option("--site", required=True, help="Site ID (e.g. SITE-001)")
@click.option("--days", default=365, show_default=True, help="License duration in days")
@click.option("--cameras", default=None, type=int, help="Camera limit (defaults per plan)")
@click.option("--plan", type=click.Choice(["smb", "mid", "enterprise"]), default="smb")
@click.option("--grace", default=14, show_default=True, help="Grace period days after expiry")
@click.option("--warning", default=30, show_default=True, help="Days before expiry to show warning")
@click.option("--private-key", required=True, type=click.Path(exists=True), help="Ed25519 private key PEM")
@click.option("--out", default=None, help="Output path for token file (prints to stdout if omitted)")
@click.option("--invoice", default=None, help="Invoice reference number")
@click.option("--notes", default=None, help="Free-text notes")
@click.option("--mb", default="unknown", help="Motherboard serial (for hardware binding)")
@click.option("--cpu", default="unknown", help="CPU ID")
@click.option("--disk", default="unknown", help="Disk serial")
@click.option("--mac", default="unknown", help="Primary MAC address")
def issue(
    client, site, days, cameras, plan, grace, warning,
    private_key, out, invoice, notes, mb, cpu, disk, mac,
):
    """Issue a new license token."""
    tier = PlanTier(plan)
    cam_limit = cameras or _DEFAULT_CAMERAS[tier]
    features = _DEFAULT_FEATURES[tier]
    fingerprint = _parse_fingerprint(mb, cpu, disk, mac)

    now = datetime.now(tz=timezone.utc)
    license_id = f"LIC-{uuid.uuid4().hex[:8].upper()}"

    claims = LicenseClaims(
        license_id=license_id,
        client_name=client,
        site_id=site,
        fingerprint=fingerprint,
        plan_tier=tier,
        camera_limit=cam_limit,
        features=features,
        issued_at=now,
        expires_at=now + timedelta(days=days),
        grace_days=grace,
        warning_days=warning,
    )

    token = sign(claims, private_key)

    if out:
        Path(out).write_text(token + "\n")
        token_path = out
        click.echo(f"Token written to: {out}")
    else:
        click.echo(token)
        token_path = None

    conn = _db()
    conn.execute(
        """INSERT INTO licenses
           (license_id, client_name, site_id, plan_tier, camera_limit,
            issued_at, expires_at, grace_days, invoice_ref, notes, token_path)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            license_id, client, site, plan, cam_limit,
            claims.issued_at.isoformat(), claims.expires_at.isoformat(),
            grace, invoice, notes, token_path,
        ),
    )
    conn.commit()
    conn.close()

    click.echo(f"License ID: {license_id}")
    click.echo(f"Expires:    {claims.expires_at.date()}")
    click.echo(f"Plan:       {plan}  Cameras: {cam_limit}")


@cli.command()
@click.argument("token_path", type=click.Path(exists=True))
@click.option("--public-key", default=None, type=click.Path(exists=True), help="Override public key")
def inspect(token_path, public_key):
    """Decode and display a license token."""
    from drishtiai_licensing.token import InvalidLicenseError
    token_str = Path(token_path).read_text().strip()
    try:
        claims = verify(token_str, public_key)
    except InvalidLicenseError as exc:
        click.secho(f"INVALID: {exc}", fg="red", err=True)
        raise SystemExit(1)

    now = datetime.now(tz=timezone.utc)
    days = claims.days_until_expiry(now)
    status = "VALID" if days > 0 else "EXPIRED"

    click.echo(f"License ID:    {claims.license_id}")
    click.echo(f"Client:        {claims.client_name}")
    click.echo(f"Site:          {claims.site_id}")
    click.echo(f"Plan:          {claims.plan_tier.value}  (cameras: {claims.camera_limit})")
    click.echo(f"Features:      {', '.join(sorted(claims.features))}")
    click.echo(f"Issued:        {claims.issued_at.date()}")
    click.echo(f"Expires:       {claims.expires_at.date()}  [{status}, {days} day(s)]")
    click.echo(f"Grace:         {claims.grace_days} day(s)")
    click.echo(f"Fingerprint:   MB={claims.fingerprint.motherboard}  CPU={claims.fingerprint.cpu}")
    click.echo(f"               DISK={claims.fingerprint.disk}  MAC={claims.fingerprint.mac}")


@cli.command("list")
@click.option("--active-only", is_flag=True, default=False)
def list_licenses(active_only):
    """List all issued licenses."""
    conn = _db()
    rows = conn.execute(
        "SELECT * FROM licenses" + (" WHERE revoked=0" if active_only else "") + " ORDER BY issued_at DESC"
    ).fetchall()
    conn.close()

    if not rows:
        click.echo("No licenses on record.")
        return

    for r in rows:
        revoked = " [REVOKED]" if r["revoked"] else ""
        click.echo(
            f"{r['license_id']}  {r['client_name']:<30} {r['site_id']:<12} "
            f"{r['plan_tier']:<12} cameras={r['camera_limit']}  "
            f"expires={r['expires_at'][:10]}{revoked}"
        )


@cli.command()
@click.argument("license_id")
@click.option("--reason", default="", help="Reason for revocation (stored in notes)")
def revoke(license_id, reason):
    """Mark a license as revoked (does not invalidate the token cryptographically)."""
    conn = _db()
    cur = conn.execute(
        "UPDATE licenses SET revoked=1, notes=COALESCE(notes||' | ','')|| ? WHERE license_id=?",
        (f"REVOKED: {reason}", license_id),
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        click.secho(f"License ID not found: {license_id}", fg="red", err=True)
        raise SystemExit(1)
    click.echo(f"Marked {license_id} as revoked.")
    click.echo("Note: to fully block the site, issue a new token with a past expiry date.")


if __name__ == "__main__":
    cli()
