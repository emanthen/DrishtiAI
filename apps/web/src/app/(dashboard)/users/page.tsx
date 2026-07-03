"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/auth";
import { API_BASE } from "@/lib/api";

const ROLE_COLORS: Record<string, string> = {
  superadmin: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300",
  site_admin: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  manager: "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300",
  guard: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  resident: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  auditor: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
};

const ALL_ROLES = ["manager", "guard", "resident", "auditor", "site_admin", "superadmin"];

interface UserRecord {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  role: string;
  site_ids: string[];
  is_active: boolean;
  created_at: string;
}

interface CreateForm {
  name: string;
  email: string;
  phone: string;
  role: string;
  password: string;
}

const EMPTY_FORM: CreateForm = { name: "", email: "", phone: "", role: "guard", password: "" };

async function apiFetch(path: string, token: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers as Record<string, string>),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

export default function UsersPage() {
  const { accessToken, user: me } = useAuthStore();
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [generatedPwd, setGeneratedPwd] = useState<string | null>(null);
  const [resettingId, setResettingId] = useState<string | null>(null);
  const [resetPwd, setResetPwd] = useState<{ id: string; pwd: string } | null>(null);
  const [filterRole, setFilterRole] = useState("");
  const [filterActive, setFilterActive] = useState<"" | "true" | "false">("");

  async function load() {
    if (!accessToken) return;
    const params = new URLSearchParams();
    if (filterRole) params.set("role", filterRole);
    if (filterActive) params.set("is_active", filterActive);
    try {
      const data = await apiFetch(`/users?${params}`, accessToken);
      setUsers(data);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { load(); }, [filterRole, filterActive]);

  async function handleCreate() {
    if (!accessToken) return;
    setCreateError(null);
    setCreating(true);
    try {
      const body: Record<string, unknown> = {
        name: form.name.trim(),
        email: form.email.trim(),
        role: form.role,
      };
      if (form.phone.trim()) body.phone = form.phone.trim();
      if (form.password.trim()) body.password = form.password.trim();
      const res = await apiFetch("/users", accessToken, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setGeneratedPwd(res.password);
      setForm(EMPTY_FORM);
      setShowCreate(false);
      load();
    } catch (e: any) {
      setCreateError(e.message);
    } finally {
      setCreating(false);
    }
  }

  async function toggleActive(u: UserRecord) {
    if (!accessToken) return;
    if (u.id === me?.id) return;
    try {
      await apiFetch(`/users/${u.id}`, accessToken, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !u.is_active }),
      });
      setUsers((prev) => prev.map((x) => x.id === u.id ? { ...x, is_active: !u.is_active } : x));
    } catch {}
  }

  async function resetPassword(id: string) {
    if (!accessToken) return;
    setResettingId(id);
    try {
      const res = await apiFetch(`/users/${id}/set-password`, accessToken, {
        method: "POST",
        body: "{}",
      });
      setResetPwd({ id, pwd: res.password });
    } catch {}
    setResettingId(null);
  }

  const canWrite = me?.role === "superadmin" || me?.role === "site_admin";

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink dark:text-bone">Users</h1>
          <p className="text-sm text-steel mt-0.5">{users.length} user{users.length !== 1 ? "s" : ""}</p>
        </div>
        {canWrite && (
          <button
            onClick={() => { setShowCreate(true); setCreateError(null); setGeneratedPwd(null); }}
            className="px-4 py-2 rounded-lg text-sm font-semibold bg-signal text-white hover:bg-signal/90 transition-colors"
          >
            + Add user
          </button>
        )}
      </div>

      {/* Generated password banner */}
      {generatedPwd && (
        <div className="mb-4 rounded-xl border border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-950/30 px-5 py-3 flex items-center justify-between">
          <span className="text-sm text-green-800 dark:text-green-300">
            User created. Temporary password: <code className="font-mono font-bold">{generatedPwd}</code>
          </span>
          <button onClick={() => setGeneratedPwd(null)} className="text-green-600 ml-4 text-lg leading-none">×</button>
        </div>
      )}

      {/* Reset password banner */}
      {resetPwd && (
        <div className="mb-4 rounded-xl border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/30 px-5 py-3 flex items-center justify-between">
          <span className="text-sm text-blue-800 dark:text-blue-300">
            New password for {users.find((u) => u.id === resetPwd.id)?.name}: <code className="font-mono font-bold">{resetPwd.pwd}</code>
          </span>
          <button onClick={() => setResetPwd(null)} className="text-blue-600 ml-4 text-lg leading-none">×</button>
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="mb-6 bg-bone dark:bg-surface border border-hairline dark:border-hairline-dark rounded-xl p-5">
          <h2 className="font-semibold text-ink dark:text-bone mb-4">New user</h2>
          {createError && <p className="text-sm text-red-500 mb-3">{createError}</p>}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-steel uppercase tracking-wide">Name *</label>
              <input
                className="mt-1 w-full border border-hairline dark:border-hairline-dark rounded-lg px-3 py-2 text-sm bg-white dark:bg-ink text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Full name"
              />
            </div>
            <div>
              <label className="text-xs text-steel uppercase tracking-wide">Email *</label>
              <input
                type="email"
                className="mt-1 w-full border border-hairline dark:border-hairline-dark rounded-lg px-3 py-2 text-sm bg-white dark:bg-ink text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="user@example.com"
              />
            </div>
            <div>
              <label className="text-xs text-steel uppercase tracking-wide">Role *</label>
              <select
                className="mt-1 w-full border border-hairline dark:border-hairline-dark rounded-lg px-3 py-2 text-sm bg-white dark:bg-ink text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                {(me?.role === "superadmin" ? ALL_ROLES : ALL_ROLES.slice(0, 4)).map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-steel uppercase tracking-wide">Phone</label>
              <input
                className="mt-1 w-full border border-hairline dark:border-hairline-dark rounded-lg px-3 py-2 text-sm bg-white dark:bg-ink text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="+977 98XXXXXXXX"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs text-steel uppercase tracking-wide">Password (leave blank to auto-generate)</label>
              <input
                type="password"
                className="mt-1 w-full border border-hairline dark:border-hairline-dark rounded-lg px-3 py-2 text-sm bg-white dark:bg-ink text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="Auto-generate"
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleCreate}
              disabled={creating || !form.name || !form.email}
              className="px-4 py-2 rounded-lg text-sm font-semibold bg-signal text-white hover:bg-signal/90 disabled:opacity-50 transition-colors"
            >
              {creating ? "Creating…" : "Create user"}
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 rounded-lg text-sm font-semibold border border-hairline dark:border-hairline-dark text-steel hover:text-ink dark:hover:text-bone transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          className="border border-hairline dark:border-hairline-dark rounded-lg px-3 py-1.5 text-sm bg-bone dark:bg-surface text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
        >
          <option value="">All roles</option>
          {ALL_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <select
          className="border border-hairline dark:border-hairline-dark rounded-lg px-3 py-1.5 text-sm bg-bone dark:bg-surface text-ink dark:text-bone focus:outline-none focus:ring-2 focus:ring-signal"
          value={filterActive}
          onChange={(e) => setFilterActive(e.target.value as "" | "true" | "false")}
        >
          <option value="">All status</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <p className="text-steel text-sm">Loading…</p>
      ) : users.length === 0 ? (
        <p className="text-steel text-sm">No users found.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-hairline dark:border-hairline-dark">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-hairline dark:border-hairline-dark bg-bone dark:bg-surface">
                <th className="text-left px-4 py-3 font-semibold text-steel uppercase text-xs tracking-wide">Name</th>
                <th className="text-left px-4 py-3 font-semibold text-steel uppercase text-xs tracking-wide">Email</th>
                <th className="text-left px-4 py-3 font-semibold text-steel uppercase text-xs tracking-wide">Role</th>
                <th className="text-left px-4 py-3 font-semibold text-steel uppercase text-xs tracking-wide">Status</th>
                <th className="text-left px-4 py-3 font-semibold text-steel uppercase text-xs tracking-wide">Created</th>
                {canWrite && <th className="px-4 py-3" />}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.id}
                  className="border-b border-hairline dark:border-hairline-dark last:border-0 hover:bg-hairline/30 dark:hover:bg-hairline-dark/30 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-ink dark:text-bone">
                    {u.name}
                    {u.id === me?.id && (
                      <span className="ml-2 text-xs text-steel">(you)</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-steel">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${ROLE_COLORS[u.role] ?? ""}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                      u.is_active
                        ? "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300"
                        : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                    }`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-steel text-xs">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  {canWrite && (
                    <td className="px-4 py-3">
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => resetPassword(u.id)}
                          disabled={resettingId === u.id}
                          className="text-xs px-2.5 py-1 rounded-md border border-hairline dark:border-hairline-dark text-steel hover:text-ink dark:hover:text-bone transition-colors disabled:opacity-50"
                        >
                          {resettingId === u.id ? "…" : "Reset pwd"}
                        </button>
                        {u.id !== me?.id && (
                          <button
                            onClick={() => toggleActive(u)}
                            className={`text-xs px-2.5 py-1 rounded-md border transition-colors ${
                              u.is_active
                                ? "border-red-300 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20"
                                : "border-green-300 text-green-600 hover:bg-green-50 dark:hover:bg-green-950/20"
                            }`}
                          >
                            {u.is_active ? "Deactivate" : "Activate"}
                          </button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
