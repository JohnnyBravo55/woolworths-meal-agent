import { Button } from "./ui/Button";

interface Props {
  onBack?: () => void;
  backLabel?: string;
  onForward?: () => void;
  showForward?: boolean;
  forwardLabel?: string;
  children?: React.ReactNode;
  className?: string;
}

export function WizardNav({
  onBack,
  backLabel = "← Back",
  onForward,
  showForward,
  forwardLabel = "Forward →",
  children,
  className = "",
}: Props) {
  if (!onBack && !showForward && !children) return null;

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      {onBack ? (
        <Button variant="secondary" onClick={onBack}>
          {backLabel}
        </Button>
      ) : null}
      {showForward && onForward ? (
        <Button variant="secondary" onClick={onForward}>
          {forwardLabel}
        </Button>
      ) : null}
      {children ? <div className="ml-auto flex flex-wrap gap-2">{children}</div> : null}
    </div>
  );
}
