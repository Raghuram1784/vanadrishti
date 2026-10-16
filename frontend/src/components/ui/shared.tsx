import type { ReactNode } from "react";
import { CircleDashed, RefreshCw } from "lucide-react";
import type { RiskLevel } from "@/types/api";
import { Button } from "./button";
export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span className={`risk-badge risk-${level.toLowerCase()}`}>
      <i />
      {level}
    </span>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <CircleDashed size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function ErrorBanner({
  text,
  retry,
}: {
  text?: string;
  retry?: () => void;
}) {
  return text ? (
    <div className="error-banner" role="alert">
      <span>{text} Previously loaded data may be stale.</span>
      {retry && (
        <Button variant="outline" size="sm" onClick={retry}>
          <RefreshCw />
          Retry
        </Button>
      )}
    </div>
  ) : null;
}
export function PageTitle({
  eyebrow,
  title,
  children,
  action,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      {action}
    </div>
  );
}
