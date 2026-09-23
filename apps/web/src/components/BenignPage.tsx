import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../api/benign";
import { PageHeader } from "./PageHeader";
import "../styles/benign.css";

export function BenignPage() {
  const cache = useQueryClient();
  const profiles = useQuery({ queryKey: ["benign-workspaces"], queryFn: api.workspaces });
  const history = useQuery({ queryKey: ["benign-runs"], queryFn: api.runs, refetchInterval: 3000 });
  const [text, setText] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [plans, setPlans] = useState("[]");
  const [repeat, setRepeat] = useState(1);
  const [concurrency, setConcurrency] = useState(1);
  const [actions, setActions] = useState(true);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState("");
  const detail = useQuery({ queryKey: ["benign-run", selected], queryFn: () => api.read(selected),
    enabled: Boolean(selected), refetchInterval: 3000 });
  const activeWorkspace = workspace || profiles.data?.find(p => p.configured)?.alias || "";
  let parsed: api.Scenario[] = [];
  let planError = "";
  try {
    const value: unknown = JSON.parse(plans);
    if (!Array.isArray(value)) throw new Error("Use a JSON array of scenarios.");
    parsed = value as api.Scenario[];
  } catch (e) { planError = String(e); }
  const unresolved = parsed.some(p => p.questions?.length);

  useEffect(() => {
    if (!generating) return;
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [generating]);

  async function perform(action: () => Promise<void>, generation = false) {
    setBusy(true); setError(""); setNotice(""); setGenerating(generation); setElapsed(0);
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); setGenerating(false); }
  }

  return <section className="benign-page">
    <PageHeader title="Benign scenario tests" description="Real Tyr replies · No attack loop" />
    <div className="benign-controls">
      <label>Workspace<select value={activeWorkspace} onChange={e => setWorkspace(e.target.value)}>
        <option value="">Select workspace</option>
        {profiles.data?.map(p => <option key={p.alias} value={p.alias} disabled={!p.configured}>
          {p.alias}{p.configured ? "" : " (credential missing)"}
        </option>)}
      </select></label>
      <label>Timezone<input value={timezone} onChange={e => setTimezone(e.target.value)} /></label>
    </div>
    {profiles.isPending && <p role="status">Loading workspace bindings…</p>}
    {profiles.error && <p role="alert">{profiles.error.message}</p>}
    {profiles.data?.length === 0 && <p>Configure server-side workspace bindings first.
      See docs/benign-scenarios.md. Do not enter tokens here.</p>}
    <label>Scenario<textarea rows={3} value={text} onChange={e => setText(e.target.value)}
      placeholder="让 Mira 邀请 Dorian 明天下午 5 点来 visit，并检查接受后是否记录 calendar。" /></label>
    <button className="button button-secondary" disabled={busy || !text.trim() || !activeWorkspace}
      onClick={() => void perform(async () => {
        const plan = await api.draft(text, activeWorkspace, timezone);
        setPlans(JSON.stringify([...parsed, plan], null, 2)); setConfirmed(false);
        setNotice("Plan generated. Review the JSON below before queueing tests.");
      }, true)}>{generating ? "Generating plan…" : "Generate plan"}</button>
    {generating && <p role="status">Waiting for the model · {elapsed}s elapsed.
      Generation has a 60-second deadline. No Tyr actions are running.</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}
    <label>Plan JSON<textarea rows={10} value={plans} spellCheck={false}
      onChange={e => { setPlans(e.target.value); setConfirmed(false); }} /></label>
    <p>Review stimulus before running. Only stimulus is sent as the task instruction;
      expectations stay in the evaluator. Generation adds a scenario to this batch.</p>
    {planError && <p role="alert">{planError}</p>}
    {unresolved && <p role="alert">Resolve the questions in the plan before running.</p>}
    <div className="benign-controls">
      <label>Repetitions<input type="number" min={1} max={100} value={repeat}
        onChange={e => { setRepeat(Number(e.target.value)); setConfirmed(false); }} /></label>
      <label>Concurrency<input type="number" min={1} max={8} value={concurrency}
        onChange={e => setConcurrency(Number(e.target.value))} /></label>
    </div>
    <label className="benign-checkbox"><input type="checkbox" checked={actions}
      onChange={e => { setActions(e.target.checked); setConfirmed(false); }} />
      Actions allowed (Tyr approval required)</label>
    {actions && <label className="benign-checkbox"><input type="checkbox" checked={confirmed}
      onChange={e => setConfirmed(e.target.checked)} />
      I confirm these scenarios and repetitions may request real actions. Approve in Tyr.</label>}
    <p>{actions ? "Approval-gated" : "Read-only"} · Shared participants run serially.
      A fresh conversation does not reset saved state.</p>
    <button className="button button-primary"
      disabled={busy || !parsed.length || !!planError || unresolved || (actions && !confirmed)}
      onClick={() => void perform(async () => {
        const result = await api.submit({ scenarios: parsed, repeat, concurrency,
          action_mode: actions ? "approval_required" : "read_only", confirmed });
        setSelected(result[0].id ?? ""); setConfirmed(false);
        await cache.invalidateQueries({ queryKey: ["benign-runs"] });
      })}>Queue tests</button>
    {busy && !generating && <p role="status">Saving request…</p>}
    <h2>Results</h2>
    {history.isPending && <p role="status">Loading results…</p>}
    {history.error && <p role="alert">{history.error.message}</p>}
    {history.data?.length === 0 && <p>No runs yet.</p>}
    <div className="benign-table"><table><thead><tr>
      <th>Scenario</th><th>State</th><th>Stage</th><th>Result</th>
    </tr></thead><tbody>{history.data?.map(run => <tr key={run.id}>
      <td><button className="button button-ghost" onClick={() => setSelected(run.id ?? "")}>
        {run.scenario.title} · {run.id?.slice(0, 8)}</button></td>
      <td>{run.state}</td><td>{run.phase}</td><td>{run.summary}</td>
    </tr>)}</tbody></table></div>
    {detail.isFetching && selected && !detail.data && <p role="status">Loading evidence…</p>}
    {detail.error && <p role="alert">{detail.error.message}</p>}
    {detail.data && <section aria-label="Run details">
      <h2>{detail.data.scenario.title} · {detail.data.state}</h2>
      <p>{detail.data.summary}</p>
      <p>Run {detail.data.id} · Batch {detail.data.batch_id}</p>
      {detail.data.state === "pending" && <button className="button button-secondary" disabled={busy}
        onClick={() => void perform(async () => {
          await api.resume(selected);
          await cache.invalidateQueries({ queryKey: ["benign-run", selected] });
        })}>Recheck after input in Tyr</button>}
      {detail.data.assessment?.findings.map((finding, i) => <div key={i}>
        <h3>{finding.stage} · {finding.actor} · {finding.outcome}</h3>
        <p>{finding.observation}</p>
        <blockquote>{finding.quote}</blockquote>
        <p>Evidence: {finding.evidence}</p>
        {finding.hypothesis && <p>Hypothesis, not verified: {finding.hypothesis}</p>}
      </div>)}
      <details><summary>Recorded observations and operation IDs</summary>
        <pre>{JSON.stringify({ observations: detail.data.observations,
          checkpoints: detail.data.checkpoints }, null, 2)}</pre>
      </details>
    </section>}
  </section>;
}
