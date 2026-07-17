/**
 * @deprecated Web no longer uses Connect / extension UI (Coming soon cart).
 * Kept as a no-op export so old imports do not crash.
 */
export function WoolworthsWebConnectModal(_props: {
  visible: boolean;
  onConnected: () => void;
  onError: (message: string) => void;
  onCancel: () => void;
}) {
  return null;
}
