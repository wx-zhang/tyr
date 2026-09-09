export function LoadingStatus({ label }: { label: string }) {
  return (
    <span className="loading-status" role="status" aria-label={label}>
      <span className="tyr-waiting-spinner" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}
