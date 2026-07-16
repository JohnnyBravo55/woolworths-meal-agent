import type { FormEvent } from "react";
import { useState } from "react";
import { authLogin, authRegister } from "../api/client";
import { Button } from "./ui/Button";

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function AuthModal({ open, onClose, onSuccess }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "login") await authLogin(email, password);
      else await authRegister(email, password);
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auth failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold">{mode === "login" ? "Sign in" : "Create account"}</h2>
        <p className="mt-1 text-sm text-slate-600">For hosted multi-user deployments (Phase 2)</p>
        <form onSubmit={submit} className="mt-4 space-y-3">
          <input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          />
          <input
            type="password"
            required
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2"
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-between items-center pt-2">
            <button
              type="button"
              className="text-sm text-[var(--ww-green)]"
              onClick={() => setMode(mode === "login" ? "register" : "login")}
            >
              {mode === "login" ? "Create account" : "Sign in instead"}
            </button>
            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? "…" : mode === "login" ? "Sign in" : "Register"}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
