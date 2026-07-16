import { useState } from "react";
import {
  openWoolworthsAccount,
  openWoolworthsSignIn,
  WOOLWORTHS_ACCOUNT_URL,
  WOOLWORTHS_HOME_URL,
} from "@meal-agent/app-core";
import { getWoolworthsStatus, woolworthsSync } from "../api/client";
import { Button } from "./ui/Button";

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ConnectModal({ open, onClose, onSuccess }: Props) {
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [checking, setChecking] = useState(false);
  const [popupBlocked, setPopupBlocked] = useState(false);

  if (!open) return null;

  const openSignIn = () => {
    setError("");
    setStatus("");
    const opened = openWoolworthsSignIn();
    setPopupBlocked(opened === null);
    setStatus(
      "In the Woolworths tab, click Sign in (top right), complete login, then click I've signed in below.",
    );
  };

  const verifySignedIn = async () => {
    setChecking(true);
    setError("");
    setStatus("Reading cookies from your browser and verifying sign-in…");
    try {
      const res = await woolworthsSync();
      if (!res.connected) {
        setError(res.message);
        setStatus("");
        return;
      }
      setStatus("Connected to Woolworths.");
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not verify Woolworths sign-in");
      setStatus("");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-slate-900">Connect Woolworths NZ</h2>
        <p className="mt-2 text-sm text-slate-600">
          Use <strong>Chrome, Edge, or Firefox</strong> (not Cursor&apos;s built-in browser). Open
          Woolworths, click <strong>Sign in</strong>, then click <strong>I&apos;ve signed in</strong>{" "}
          here.
        </p>
        {popupBlocked && (
          <p className="mt-3 text-sm text-amber-800 bg-amber-50 rounded-lg p-3">
            Pop-up blocked.{" "}
            <a href={WOOLWORTHS_HOME_URL} target="_blank" rel="noreferrer" className="underline">
              Open woolworths.co.nz
            </a>{" "}
            or{" "}
            <a href={WOOLWORTHS_ACCOUNT_URL} target="_blank" rel="noreferrer" className="underline">
              account.woolworths.co.nz
            </a>
            .
          </p>
        )}
        {status && !error && (
          <p className="mt-3 text-sm text-slate-700 bg-slate-50 rounded-lg p-3">{status}</p>
        )}
        {checking && (
          <p className="mt-3 text-sm text-amber-800 bg-amber-50 rounded-lg p-3 animate-pulse">
            Checking Woolworths connection…
          </p>
        )}
        {error && (
          <p className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            {error}
          </p>
        )}
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={checking}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              openWoolworthsAccount();
              setStatus("Sign in on the account page, then visit woolworths.co.nz and click I've signed in.");
            }}
            disabled={checking}
          >
            Account login
          </Button>
          <Button type="button" variant="secondary" onClick={openSignIn} disabled={checking}>
            Open Woolworths
          </Button>
          <Button type="button" onClick={verifySignedIn} disabled={checking}>
            {checking ? "Checking…" : "I've signed in"}
          </Button>
        </div>
      </div>
    </div>
  );
}
