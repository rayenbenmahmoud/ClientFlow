import { Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { inputClass } from "../components/FormModal";

const DEMO = [
  { username: "admin", role: "Admin - everything, user management" },
  { username: "manager", role: "Manager - whole team's data" },
  { username: "rep", role: "Sales rep - own leads, deals and tasks" },
];

export function LoginPage() {
  const { user, login } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={(location.state as { from?: string } | null)?.from ?? "/"} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? "Incorrect username or password." : err instanceof ApiError && err.status === 429 ? "Too many attempts. Please wait a minute and try again." : err instanceof ApiError ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center bg-slate-900 p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3 text-white">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 font-bold">CF</span>
          <span className="text-2xl font-semibold">ClientFlow CRM</span>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6 shadow-xl">
          <h1 className="text-lg font-semibold text-slate-900">Sign in</h1>
          {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-900 ring-1 ring-rose-300">{error}</p>}
          <div>
            <label htmlFor="username" className="mb-1 block text-sm font-medium text-slate-800">Username</label>
            <input id="username" className={inputClass} autoComplete="username" required autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-slate-800">Password</label>
            <input id="password" type="password" className={inputClass} autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
            {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />} Sign in
          </button>
        </form>
        <div className="mt-4 rounded-xl bg-slate-800 p-4 text-sm text-slate-200">
          <p className="font-medium text-white">Demo accounts (fictional data)</p>
          <ul className="mt-2 space-y-1">
            {DEMO.map((d) => (
              <li key={d.username}>
                <button type="button" onClick={() => setUsername(d.username)} className="text-left hover:text-white">
                  <code className="rounded bg-slate-700 px-1.5 py-0.5 text-white">{d.username}</code> <span className="text-slate-300">{d.role}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-300">Password is printed by <code>seed_demo</code> (see README).</p>
        </div>
      </div>
    </div>
  );
}
