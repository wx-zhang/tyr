type StatusTone = "info" | "success" | "warning" | "danger" | "neutral";

type StatusBadgeProps = {
  label: string;
  tone?: StatusTone;
  pulse?: boolean;
};

export function StatusBadge({
  label,
  tone = "neutral",
  pulse = false,
}: StatusBadgeProps) {
  return (
    <span className={`status-badge status-${tone}`}>
      <span
        className={`status-dot${pulse ? " status-dot-pulse" : ""}`}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}
