"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "@/store/auth";
import { api, Site, Tariff, TariffCreate } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";

// ── Timezone options (South Asia + UTC + common international) ────────────────
const TIMEZONES = [
  "Asia/Kathmandu",
  "Asia/Kolkata",
  "Asia/Dhaka",
  "Asia/Colombo",
  "Asia/Karachi",
  "Asia/Thimphu",
  "Asia/Yangon",
  "UTC",
  "Asia/Dubai",
  "Asia/Singapore",
  "Europe/London",
  "America/New_York",
];

const PLATE_REGIONS = [
  { value: "NP", label: "Nepal (NP)" },
  { value: "IN", label: "India (IN)" },
  { value: "BD", label: "Bangladesh (BD)" },
  { value: "LK", label: "Sri Lanka (LK)" },
  { value: "PK", label: "Pakistan (PK)" },
];

type Tab = "site" | "tariffs";

// ── Tariff rules types ────────────────────────────────────────────────────────

interface FixedTier {
  kind: "fixed";
  up_to_minutes: number;
  charge: number;
}

interface HourlyTier {
  kind: "hourly";
  per_hour: number;
  max_per_day: number | "";
}

type TariffTier = FixedTier | HourlyTier;

interface TariffForm {
  name: string;
  grace_minutes: number;
  tiers: TariffTier[];
}

function defaultForm(): TariffForm {
  return {
    name: "",
    grace_minutes: 0,
    tiers: [
      { kind: "fixed", up_to_minutes: 60, charge: 0 },
      { kind: "hourly", per_hour: 20, max_per_day: "" },
    ],
  };
}

function formToRulesJson(form: TariffForm): Record<string, unknown> {
  return {
    grace_minutes: form.grace_minutes,
    tiers: form.tiers.map((t) => {
      if (t.kind === "fixed") {
        return { up_to_minutes: t.up_to_minutes, charge: t.charge };
      }
      const tier: Record<string, unknown> = { per_hour: t.per_hour };
      if (t.max_per_day !== "" && t.max_per_day !== undefined) {
        tier.max_per_day = Number(t.max_per_day);
      }
      return tier;
    }),
  };
}

function rulesJsonToForm(name: string, rules: Record<string, unknown>): TariffForm {
  const tiers = (rules.tiers as unknown[] | undefined) ?? [];
  return {
    name,
    grace_minutes: Number(rules.grace_minutes ?? 0),
    tiers: tiers.map((t): TariffTier => {
      const obj = t as Record<string, unknown>;
      if ("per_hour" in obj) {
        return {
          kind: "hourly",
          per_hour: Number(obj.per_hour),
          max_per_day: obj.max_per_day != null ? Number(obj.max_per_day) : "",
        };
      }
      return {
        kind: "fixed",
        up_to_minutes: Number(obj.up_to_minutes ?? 60),
        charge: Number(obj.charge ?? 0),
      };
    }),
  };
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { accessToken } = useAuthStore();
  const [tab, setTab] = useState<Tab>("site");
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!accessToken) return;
    api.sites.list(accessToken).then((s) => {
      setSites(s);
      if (s.length > 0) setSelectedSiteId(s[0].id);
    }).finally(() => setLoading(false));
  }, [accessToken]);

  const selectedSite = sites.find((s) => s.id === selectedSiteId) ?? null;

  if (loading) return <div className="p-8 text-steel text-sm">Loading…</div>;

  return (
    <div className="p-8 max-w-3xl space-y-6">
      <PageHeader
        title="Settings"
        description="Site configuration and parking tariffs"
      />

      {sites.length > 1 && (
        <div className="flex items-center gap-3">
          <span className="text-xs text-steel font-medium">Site</span>
          <Select
            value={selectedSiteId}
            onChange={(e) => setSelectedSiteId(e.target.value)}
            className="w-56"
          >
            {sites.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </Select>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-hairline dark:border-hairline-dark">
        {(["site", "tariffs"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors ${
              tab === t
                ? "border-b-2 border-signal text-ink dark:text-bone -mb-px"
                : "text-steel hover:text-ink dark:hover:text-bone"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {selectedSite ? (
        tab === "site" ? (
          <SiteSettingsTab
            site={selectedSite}
            token={accessToken!}
            onSaved={(updated) =>
              setSites((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
            }
          />
        ) : (
          <TariffsTab siteId={selectedSiteId} token={accessToken!} />
        )
      ) : (
        <div className="text-steel text-sm">No sites found.</div>
      )}
    </div>
  );
}

// ── Site settings tab ─────────────────────────────────────────────────────────

function SiteSettingsTab({
  site,
  token,
  onSaved,
}: {
  site: Site;
  token: string;
  onSaved: (s: Site) => void;
}) {
  const [name, setName] = useState(site.name);
  const [address, setAddress] = useState(site.address ?? "");
  const [timezone, setTimezone] = useState(site.timezone);
  const [plateRegion, setPlateRegion] = useState(site.plate_region);
  const [gateExpiryMode, setGateExpiryMode] = useState(site.gate_expiry_mode ?? "manual");
  const [recordOnExpiry, setRecordOnExpiry] = useState(site.record_on_expiry ?? false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(site.name);
    setAddress(site.address ?? "");
    setTimezone(site.timezone);
    setPlateRegion(site.plate_region);
    setGateExpiryMode(site.gate_expiry_mode ?? "manual");
    setRecordOnExpiry(site.record_on_expiry ?? false);
    setSaved(false);
  }, [site.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSave() {
    if (!name.trim()) { setError("Site name is required"); return; }
    setError(null);
    setSaving(true);
    try {
      const updated = await api.sites.patch(token, site.id, {
        name: name.trim(),
        address: address.trim() || undefined,
        timezone,
        plate_region: plateRegion,
        gate_expiry_mode: gateExpiryMode as "manual" | "freeflow",
        record_on_expiry: recordOnExpiry,
      });
      onSaved(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <Field label="Site name">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Main entrance" />
      </Field>
      <Field label="Address">
        <Input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Kathmandu, Nepal" />
      </Field>
      <Field label="Timezone">
        <Select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
          {TIMEZONES.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
        </Select>
      </Field>
      <Field label="Plate region">
        <Select value={plateRegion} onChange={(e) => setPlateRegion(e.target.value)}>
          {PLATE_REGIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </Select>
      </Field>

      <hr className="border-hairline dark:border-hairline-dark" />
      <p className="text-xs font-semibold text-steel uppercase tracking-wide">License expiry behaviour</p>

      <Field label="Gate expiry mode" hint="What happens to the gate relay when the license expires">
        <Select value={gateExpiryMode} onChange={(e) => setGateExpiryMode(e.target.value)}>
          <option value="manual">Manual — gate stays in its current position (default)</option>
          <option value="freeflow">Free-flow — gate pulses open (parking exits, accessible entrances)</option>
        </Select>
      </Field>

      <Field label="Record events on expiry" hint="Continue writing plate read events to the database even after license expires">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={recordOnExpiry}
            onChange={(e) => setRecordOnExpiry(e.target.checked)}
            className="rounded border-hairline accent-signal"
          />
          <span className="text-sm text-ink dark:text-bone">Keep recording after expiry</span>
        </label>
      </Field>

      {error && <p className="text-xs text-alert">{error}</p>}
      {saved && <p className="text-xs text-confirm font-medium">Saved.</p>}

      <div className="flex gap-3">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </div>
  );
}

// ── Tariffs tab ───────────────────────────────────────────────────────────────

function TariffsTab({ siteId, token }: { siteId: string; token: string }) {
  const [tariffs, setTariffs] = useState<Tariff[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editTarget, setEditTarget] = useState<Tariff | null>(null);

  const reload = useCallback(async () => {
    const list = await api.tariffs.list(token, siteId);
    setTariffs(list);
  }, [token, siteId]);

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, [reload]);

  async function toggleActive(t: Tariff) {
    await api.tariffs.patch(token, t.id, { active: !t.active });
    await reload();
  }

  async function deleteTariff(id: string) {
    if (!confirm("Delete this tariff? This cannot be undone.")) return;
    await api.tariffs.delete(token, id);
    await reload();
  }

  function openCreate() { setEditTarget(null); setShowForm(true); }
  function openEdit(t: Tariff) { setEditTarget(t); setShowForm(true); }
  function closeForm() { setShowForm(false); setEditTarget(null); }

  if (loading) return <div className="text-steel text-sm">Loading…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-steel">
          Only one tariff should be active at a time. The active tariff is applied to all new parking sessions.
        </p>
        <Button size="sm" onClick={openCreate}>+ New tariff</Button>
      </div>

      {tariffs.length === 0 && !showForm && (
        <div className="border border-dashed border-hairline dark:border-hairline-dark rounded p-8 text-center text-steel text-sm">
          No tariffs configured. Add one to enable parking billing.
        </div>
      )}

      {tariffs.map((t) => (
        <TariffCard
          key={t.id}
          tariff={t}
          onToggle={() => toggleActive(t)}
          onEdit={() => openEdit(t)}
          onDelete={() => deleteTariff(t.id)}
        />
      ))}

      {showForm && (
        <TariffFormPanel
          siteId={siteId}
          token={token}
          existing={editTarget}
          onDone={() => { closeForm(); reload(); }}
          onCancel={closeForm}
        />
      )}
    </div>
  );
}

function TariffCard({
  tariff,
  onToggle,
  onEdit,
  onDelete,
}: {
  tariff: Tariff;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const rules = tariff.rules_json as { grace_minutes?: number; tiers?: unknown[] };
  const tierCount = rules.tiers?.length ?? 0;
  return (
    <div className="border border-hairline dark:border-hairline-dark rounded-lg p-4 flex items-start justify-between gap-4">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-ink dark:text-bone">{tariff.name}</span>
          {tariff.active ? (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-confirm/15 text-confirm">ACTIVE</span>
          ) : (
            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-steel/15 text-steel">INACTIVE</span>
          )}
        </div>
        <p className="text-xs text-steel">
          Grace {rules.grace_minutes ?? 0} min · {tierCount} tier{tierCount !== 1 ? "s" : ""}
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Button variant="ghost" size="sm" onClick={onToggle}>
          {tariff.active ? "Deactivate" : "Activate"}
        </Button>
        <Button variant="outline" size="sm" onClick={onEdit}>Edit</Button>
        <Button variant="danger" size="sm" onClick={onDelete}>Delete</Button>
      </div>
    </div>
  );
}

// ── Tariff form ───────────────────────────────────────────────────────────────

function TariffFormPanel({
  siteId,
  token,
  existing,
  onDone,
  onCancel,
}: {
  siteId: string;
  token: string;
  existing: Tariff | null;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<TariffForm>(
    existing
      ? rulesJsonToForm(existing.name, existing.rules_json)
      : defaultForm()
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function setName(v: string) { setForm((f) => ({ ...f, name: v })); }
  function setGrace(v: string) { setForm((f) => ({ ...f, grace_minutes: Number(v) || 0 })); }

  function updateTier(i: number, patch: Partial<TariffTier>) {
    setForm((f) => {
      const tiers = [...f.tiers];
      tiers[i] = { ...tiers[i], ...patch } as TariffTier;
      return { ...f, tiers };
    });
  }

  function addTier(kind: "fixed" | "hourly") {
    const tier: TariffTier =
      kind === "fixed"
        ? { kind: "fixed", up_to_minutes: 60, charge: 0 }
        : { kind: "hourly", per_hour: 20, max_per_day: "" };
    setForm((f) => ({ ...f, tiers: [...f.tiers, tier] }));
  }

  function removeTier(i: number) {
    setForm((f) => ({ ...f, tiers: f.tiers.filter((_, idx) => idx !== i) }));
  }

  async function handleSave() {
    if (!form.name.trim()) { setError("Tariff name is required"); return; }
    setError(null);
    setSaving(true);
    try {
      const body: TariffCreate = {
        site_id: siteId,
        name: form.name.trim(),
        rules_json: formToRulesJson(form),
      };
      if (existing) {
        await api.tariffs.patch(token, existing.id, body);
      } else {
        await api.tariffs.create(token, body);
      }
      onDone();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="border border-signal/40 rounded-lg p-5 space-y-5 bg-surface dark:bg-surface">
      <p className="text-sm font-semibold text-ink dark:text-bone">
        {existing ? "Edit tariff" : "New tariff"}
      </p>

      <Field label="Name">
        <Input value={form.name} onChange={(e) => setName(e.target.value)} placeholder="Standard daytime" />
      </Field>

      <Field label="Grace period (minutes)" hint="Free time before billing starts">
        <Input
          type="number"
          min={0}
          value={form.grace_minutes}
          onChange={(e) => setGrace(e.target.value)}
          className="w-32"
        />
      </Field>

      <div className="space-y-3">
        <p className="text-xs font-semibold text-steel uppercase tracking-wide">Billing tiers</p>

        {form.tiers.map((tier, i) => (
          <div key={i} className="border border-hairline dark:border-hairline-dark rounded p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-steel">
                Tier {i + 1} — {tier.kind === "fixed" ? "Flat rate" : "Hourly rate"}
              </span>
              <button
                onClick={() => removeTier(i)}
                className="text-xs text-alert hover:underline"
              >
                Remove
              </button>
            </div>

            {tier.kind === "fixed" ? (
              <div className="flex items-center gap-4 flex-wrap">
                <label className="flex items-center gap-2 text-xs text-steel">
                  Up to
                  <Input
                    type="number"
                    min={1}
                    value={(tier as FixedTier).up_to_minutes}
                    onChange={(e) => updateTier(i, { up_to_minutes: Number(e.target.value) })}
                    className="w-20"
                  />
                  minutes
                </label>
                <label className="flex items-center gap-2 text-xs text-steel">
                  Flat charge NPR
                  <Input
                    type="number"
                    min={0}
                    value={(tier as FixedTier).charge}
                    onChange={(e) => updateTier(i, { charge: Number(e.target.value) })}
                    className="w-24"
                  />
                </label>
              </div>
            ) : (
              <div className="flex items-center gap-4 flex-wrap">
                <label className="flex items-center gap-2 text-xs text-steel">
                  NPR
                  <Input
                    type="number"
                    min={1}
                    value={(tier as HourlyTier).per_hour}
                    onChange={(e) => updateTier(i, { per_hour: Number(e.target.value) })}
                    className="w-20"
                  />
                  / hour
                </label>
                <label className="flex items-center gap-2 text-xs text-steel">
                  Daily cap NPR
                  <Input
                    type="number"
                    min={0}
                    value={(tier as HourlyTier).max_per_day}
                    onChange={(e) => updateTier(i, { max_per_day: e.target.value === "" ? "" : Number(e.target.value) })}
                    placeholder="none"
                    className="w-24"
                  />
                </label>
              </div>
            )}
          </div>
        ))}

        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => addTier("fixed")}>
            + Add flat-rate tier
          </Button>
          <Button variant="ghost" size="sm" onClick={() => addTier("hourly")}>
            + Add hourly tier
          </Button>
        </div>
      </div>

      {error && <p className="text-xs text-alert">{error}</p>}

      <div className="flex gap-3">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : existing ? "Save changes" : "Create tariff"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

// ── Field helper ──────────────────────────────────────────────────────────────

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-steel uppercase tracking-wide">
        {label}
      </label>
      {hint && <p className="text-xs text-steel/70">{hint}</p>}
      {children}
    </div>
  );
}
