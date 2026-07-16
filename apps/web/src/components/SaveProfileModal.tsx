import { Button } from "./ui/Button";

interface Props {
  open: boolean;
  onClose: () => void;
  onSave: (name: string) => void;
  saving?: boolean;
}

export function SaveProfileModal({ open, onClose, onSave, saving }: Props) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <form
        className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const name = (new FormData(form).get("profileName") as string)?.trim();
          if (name) onSave(name);
        }}
      >
        <h3 className="font-semibold text-slate-900">Save profile</h3>
        <p className="mt-1 text-sm text-slate-600">
          Give this setup a name so you can load it later.
        </p>
        <input
          name="profileName"
          autoFocus
          required
          placeholder="e.g. Ferrymead gluten-free"
          className="mt-4 w-full rounded-lg border border-slate-300 px-3 py-2"
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </form>
    </div>
  );
}
