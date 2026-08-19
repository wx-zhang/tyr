export type HistoryCaseOrigin = "base" | "scientist" | "prior";

export type HistoryCase = {
  caseId: string;
  origin: HistoryCaseOrigin;
};

type ScientistHistoryUsedProps = {
  cases: HistoryCase[];
};

const ORIGIN_LABEL: Record<HistoryCaseOrigin, string> = {
  base: "Base",
  scientist: "Scientist",
  prior: "Prior run",
};

const ORIGIN_TITLE: Record<HistoryCaseOrigin, string> = {
  base: "Base scenarios",
  scientist: "Scientist scenarios",
  prior: "Prior-run scenarios",
};

const GROUP_ORDER: HistoryCaseOrigin[] = ["base", "scientist", "prior"];

function groupCases(cases: HistoryCase[]): Array<{
  origin: HistoryCaseOrigin;
  items: HistoryCase[];
}> {
  const buckets = new Map<HistoryCaseOrigin, HistoryCase[]>();
  for (const item of cases) {
    const list = buckets.get(item.origin) ?? [];
    list.push(item);
    buckets.set(item.origin, list);
  }
  return GROUP_ORDER.flatMap((origin) => {
    const items = buckets.get(origin);
    return items?.length ? [{ origin, items }] : [];
  });
}

function countByOrigin(cases: HistoryCase[]): Record<HistoryCaseOrigin, number> {
  return {
    base: cases.filter((item) => item.origin === "base").length,
    scientist: cases.filter((item) => item.origin === "scientist").length,
    prior: cases.filter((item) => item.origin === "prior").length,
  };
}

function padIndex(index: number): string {
  return String(index).padStart(2, "0");
}

export function ScientistHistoryUsed({ cases }: ScientistHistoryUsedProps) {
  const groups = groupCases(cases);
  const counts = countByOrigin(cases);
  const multiColumn = groups.length > 1;

  return (
    <section className="scientist-history" aria-label="Tests used from history">
      <header className="scientist-history-header">
        <div className="scientist-history-heading">
          <p className="scientist-history-label">Seed history</p>
          <p className="scientist-history-lede">
            Prior base and scientist scenarios studied for this iteration
          </p>
        </div>
        {cases.length ? (
          <div className="scientist-history-metrics" aria-hidden="true">
            <div className="scientist-history-metric">
              <span className="scientist-history-metric-value mono">
                {cases.length}
              </span>
              <span className="scientist-history-metric-label">Total</span>
            </div>
            {counts.base > 0 ? (
              <div className="scientist-history-metric origin-base">
                <span className="scientist-history-metric-value mono">
                  {counts.base}
                </span>
                <span className="scientist-history-metric-label">Base</span>
              </div>
            ) : null}
            {counts.scientist > 0 ? (
              <div className="scientist-history-metric origin-scientist">
                <span className="scientist-history-metric-value mono">
                  {counts.scientist}
                </span>
                <span className="scientist-history-metric-label">Scientist</span>
              </div>
            ) : null}
            {counts.prior > 0 ? (
              <div className="scientist-history-metric origin-prior">
                <span className="scientist-history-metric-value mono">
                  {counts.prior}
                </span>
                <span className="scientist-history-metric-label">Prior</span>
              </div>
            ) : null}
          </div>
        ) : null}
      </header>

      {!cases.length ? (
        <p className="scientist-history-empty">
          No prior tests were available.
        </p>
      ) : (
        <div
          className={`scientist-history-columns${multiColumn ? " is-split" : ""}`}
        >
          {groups.map((group) => (
            <section
              key={group.origin}
              className={`scientist-history-column origin-${group.origin}`}
              aria-label={ORIGIN_TITLE[group.origin]}
            >
              <header className="scientist-history-column-head">
                <span
                  className={`scientist-history-origin origin-${group.origin}`}
                >
                  <span
                    className="scientist-history-origin-dot"
                    aria-hidden="true"
                  />
                  {ORIGIN_LABEL[group.origin]}
                </span>
                <span className="scientist-history-column-count mono">
                  {group.items.length}
                </span>
              </header>
              <ol className="scientist-history-rows">
                {group.items.map((item, index) => (
                  <li key={item.caseId} className="scientist-history-row">
                    <span
                      className={`scientist-history-row-badge origin-${item.origin}`}
                    >
                      {ORIGIN_LABEL[item.origin]}
                    </span>
                    <span
                      className="scientist-history-index mono"
                      aria-hidden="true"
                    >
                      {padIndex(index + 1)}
                    </span>
                    <span
                      className="scientist-history-id mono"
                      title={item.caseId}
                    >
                      {item.caseId}
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      )}

      {cases.length ? (
        <p className="scientist-history-sr-summary">
          {cases.length} prior test{cases.length === 1 ? "" : "s"}
          {counts.base ? ` · ${counts.base} base` : ""}
          {counts.scientist ? ` · ${counts.scientist} scientist` : ""}
          {counts.prior ? ` · ${counts.prior} prior-run` : ""}
        </p>
      ) : null}
    </section>
  );
}

export function resolveHistoryCases(
  caseIds: string[],
  options: {
    origins?: string[] | null;
    originByCaseId?: Map<string, HistoryCaseOrigin>;
    taskCaseIds?: Iterable<string> | null;
  } = {},
): HistoryCase[] {
  const dataset = new Set(options.taskCaseIds ?? []);
  return caseIds.map((caseId, index) => {
    const fromApi = options.origins?.[index];
    if (fromApi === "base" || fromApi === "scientist") {
      return { caseId, origin: fromApi };
    }
    const mapped = options.originByCaseId?.get(caseId);
    if (mapped === "base" || mapped === "scientist") {
      return { caseId, origin: mapped };
    }
    if (dataset.size > 0) {
      return {
        caseId,
        origin: dataset.has(caseId) ? "base" : "scientist",
      };
    }
    return { caseId, origin: mapped ?? "prior" };
  });
}

export function buildCaseOriginMap(
  turns: Array<{
    stage?: string | null;
    caseId?: string | null;
    status?: string | null;
    tyrMessage?: string | null;
  }>,
  baseCaseIds?: string[] | null,
): Map<string, HistoryCaseOrigin> {
  const map = new Map<string, HistoryCaseOrigin>();
  if (baseCaseIds) {
    for (const caseId of baseCaseIds) {
      map.set(caseId, "base");
    }
  }
  for (const turn of turns) {
    if (!turn.caseId) continue;
    const scientistGeneration =
      turn.stage === "scientist" &&
      !turn.tyrMessage &&
      ["generating", "failed", "ready", "completed"].includes(
        turn.status ?? "",
      );
    if (scientistGeneration) {
      map.set(turn.caseId, "scientist");
      continue;
    }
    if (turn.stage === "case") {
      if (!map.has(turn.caseId) || map.get(turn.caseId) === "prior") {
        map.set(turn.caseId, "base");
      }
      continue;
    }
    if (turn.stage === "scientist" && map.get(turn.caseId) !== "base") {
      map.set(turn.caseId, "scientist");
    }
  }
  return map;
}
