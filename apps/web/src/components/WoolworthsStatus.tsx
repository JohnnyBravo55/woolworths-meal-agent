import { useEffect, useState } from "react";
import { getWoolworthsStatus, woolworthsDisconnect } from "../api/client";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";

interface Props {
  onConnect: () => void;
  onDisconnect?: () => void;
}

export function WoolworthsStatus({ onConnect, onDisconnect }: Props) {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [message, setMessage] = useState("");
  const [disconnecting, setDisconnecting] = useState(false);

  const refresh = () => {
    getWoolworthsStatus()
      .then((r) => {
        setConnected(r.connected);
        setMessage(r.message);
      })
      .catch(() => {
        setConnected(false);
        setMessage("Could not check status");
      });
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 30000);
    return () => clearInterval(t);
  }, []);

  const disconnect = async () => {
    setDisconnecting(true);
    try {
      const r = await woolworthsDisconnect();
      setConnected(r.connected);
      setMessage(r.message);
      onDisconnect?.();
    } catch {
      setMessage("Disconnect failed");
    } finally {
      setDisconnecting(false);
    }
  };

  if (connected === null) {
    return <Badge>Checking…</Badge>;
  }

  return (
    <div className="flex items-center gap-2">
      <Badge tone={connected ? "success" : "warning"}>
        {connected ? "● Woolworths connected" : "○ Not connected"}
      </Badge>
      {connected ? (
        <Button variant="secondary" size="sm" onClick={disconnect} disabled={disconnecting}>
          {disconnecting ? "Disconnecting…" : "Disconnect"}
        </Button>
      ) : (
        <Button variant="secondary" size="sm" onClick={onConnect}>
          Connect
        </Button>
      )}
      <span className="hidden lg:inline text-xs text-slate-500 max-w-[200px] truncate">{message}</span>
    </div>
  );
}
