import { useEffect, useRef, useState } from "react";
import type { ManagedAsha } from "./AuthPage";
import { getTeamReport, type Patient, type TeamReportRow } from "./records";

const columns = [
  ["patients", "Patients"],
  ["hb_recorded", "Hb readings"],
  ["hb_pending", "Hb pending"],
  ["anemia_confirmed", "Anemia confirmed (recorded)"],
  ["not_assessed", "Not assessed"],
  ["followups_due", "Follow-ups due today"],
  ["followups_overdue", "Follow-ups overdue"],
  ["followups_completed", "Follow-ups completed"],
  ["referrals_referred", "Referred"],
  ["referrals_attended", "Attended"],
  ["referrals_closed", "Outcomes recorded"],
] as const;

function csvCell(value: string | number) {
  const raw = String(value);
  const text = typeof value === "string" && /^[\s\uFEFF]*[=+\-@\t\r\n]/.test(raw) ? "'" + raw : raw;
  return '"' + text.replaceAll('"', '""') + '"';
}

function downloadReport(rows: TeamReportRow[]) {
  const values = [
    ["ASHA Worker", ...columns.map(([, label]) => label)],
    ...rows.map(row => [row.worker_name, ...columns.map(([key]) => row[key])]),
  ];
  const csv = values.map(row => row.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "sakhicare-team-report.csv";
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

type ReportMetric = (typeof columns)[number][0];
type ChartType = "bar" | "line" | "dot";

function TeamReportChart({ rows, metric, onMetricChange, chartType, onChartTypeChange }: {
  rows: TeamReportRow[];
  metric: ReportMetric;
  onMetricChange: (metric: ReportMetric) => void;
  chartType: ChartType;
  onChartTypeChange: (type: ChartType) => void;
}) {
  const label = columns.find(([key]) => key === metric)?.[1] ?? "";
  const maxValue = rows.reduce((max, row) => Math.max(max, row[metric]), 0);
  const tickStep = Math.max(1, Math.ceil(maxValue / 4));
  const ceiling = tickStep * 4;
  const left = 64;
  const top = 28;
  const bottom = 178;
  const plotWidth = Math.max(256, rows.length * 112);
  const slot = plotWidth / rows.length;
  const width = left + plotWidth + 16;
  const points = rows.map((row, index) => ({
    row,
    x: left + slot * (index + 0.5),
    y: bottom - (bottom - top) * row[metric] / ceiling,
  }));

  return (
    <figure className="admin-report-chart" aria-labelledby="report-chart-heading">
      <div className="admin-report-chart-header">
        <figcaption id="report-chart-heading">Compare ASHA workers</figcaption>
        <div className="admin-report-chart-controls">
          <label>Chart type
            <select value={chartType} onChange={event => onChartTypeChange(event.target.value as ChartType)}>
              <option value="bar">Bar chart</option>
              <option value="line">Line chart</option>
              <option value="dot">Dot chart</option>
            </select>
          </label>
          <label>Metric
            <select value={metric} onChange={event => onMetricChange(event.target.value as ReportMetric)}>
              {columns.map(([key, title]) => <option key={key} value={key}>{title}</option>)}
            </select>
          </label>
        </div>
      </div>
      <div className="admin-report-chart-scroll" tabIndex={0} role="region" aria-label="Chart plot">
        <svg viewBox={"0 0 " + width + " 236"} style={{ minWidth: width }} role="img"
          aria-label={label + " by ASHA worker. Exact values are available in Table view."}>
          <text x={left} y="14" className="report-axis-title">{label}</text>
          {[0, 1, 2, 3, 4].map(tick => {
            const y = bottom - (bottom - top) * tick / 4;
            return <g key={tick}>
              <line className="report-grid-line" x1={left} x2={left + plotWidth} y1={y} y2={y} />
              <text x={left - 8} y={y + 4} textAnchor="end">{tick * tickStep}</text>
            </g>;
          })}
          <path className="report-axis-line" d={"M" + left + " " + top + "V" + bottom + "H" + (left + plotWidth)} />
          {chartType === "line" && <polyline className="report-series-line"
            points={points.map(({ x, y }) => x + "," + y).join(" ")} />}
          {points.map(({ row, x, y }) => <g key={row.worker_id}>
            <title>{row.worker_name + ": " + row[metric]}</title>
            {chartType === "bar"
              ? <rect className="report-series-mark" x={x - 18} y={y} width="36" height={bottom - y} rx="3" />
              : <circle className="report-series-mark" cx={x} cy={y} r="5" />}
            <text className="report-point-value" x={x} y={y - 8} textAnchor="middle">{row[metric]}</text>
            <text x={x} y={bottom + 21} textAnchor="middle">
              {row.worker_name.length > 15 ? row.worker_name.slice(0, 14) + "…" : row.worker_name}
            </text>
          </g>)}
          <text x={left + plotWidth / 2} y="228" textAnchor="middle" className="report-axis-title">ASHA Worker</text>
        </svg>
      </div>
    </figure>
  );
}
export function AdminReports({ workers, patients }: { workers: ManagedAsha[]; patients: Patient[] }) {
  const [view, setView] = useState<"table" | "chart">("table");
  const [metric, setMetric] = useState<ReportMetric>("patients");
  const [chartType, setChartType] = useState<ChartType>("bar");
  const [filters, setFilters] = useState({ start: "", end: "", worker_id: "", village: "" });
  const [result, setResult] = useState<{ key: string; rows: TeamReportRow[] } | null>(null);
  const [failed, setFailed] = useState("");
  const [attempt, setAttempt] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const filterKey = JSON.stringify(filters);
  const dateError = filters.start && filters.end && filters.start > filters.end;
  const rows = result?.key === filterKey ? result.rows : null;
  const villages = [...new Set(patients.flatMap(patient => patient.village ? [patient.village] : []))].sort();

  useEffect(() => {
    window.scrollTo(0, 0);
    heading.current?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    if (dateError) return;
    const controller = new AbortController();
    setFailed("");
    getTeamReport(filters, controller.signal).then(rows => {
      if (!controller.signal.aborted) setResult({ key: filterKey, rows });
    }).catch(() => {
      if (!controller.signal.aborted) setFailed(filterKey);
    });
    return () => controller.abort();
  }, [filters, filterKey, dateError, attempt]);

  function change(name: keyof typeof filters, value: string) {
    setResult(null);
    setFailed("");
    setFilters(current => ({ ...current, [name]: value }));
  }

  return <>
    <header className="page-head">
      <h1 ref={heading} tabIndex={-1}>Reports</h1>
      <div className="admin-report-header-actions">
        <div className="admin-report-view-switch" role="group" aria-label="Report view">
          <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}>Table</button>
          <button type="button" aria-pressed={view === "chart"} onClick={() => setView("chart")}>Chart</button>
        </div>
        <button className="btn" type="button" disabled={!rows?.length || Boolean(dateError)}
          onClick={() => rows && downloadReport(rows)}>Export CSV</button>
      </div>
    </header>
    <section className="panel admin-report-panel" aria-label="ASHA team report">
      <div className="admin-report-filters">
        <label>From<input type="date" value={filters.start} onChange={event => change("start", event.target.value)} /></label>
        <label>To<input type="date" value={filters.end} onChange={event => change("end", event.target.value)} /></label>
        <label>ASHA Worker<select value={filters.worker_id} onChange={event => change("worker_id", event.target.value)}>
          <option value="">All workers</option>
          {workers.map(worker => <option key={worker.id} value={worker.id}>{worker.name}</option>)}
        </select></label>
        <label>Village<select value={filters.village} onChange={event => change("village", event.target.value)}>
          <option value="">All villages</option>
          {villages.map(village => <option key={village}>{village}</option>)}
        </select></label>
      </div>
      <p>Dates filter test, follow-up due and referral dates. Patient and assessment counts show current records.</p>
      {dateError ? <p role="alert">From date must be on or before To date.</p>
        : failed === filterKey ? <div role="alert">
          <p>Could not load the report.</p>
          <button className="btn subtle" type="button" onClick={() => setAttempt(value => value + 1)}>Retry</button>
        </div>
        : !rows ? <p role="status">Loading report...</p>
        : !rows.length ? <p>No workers match these filters.</p>
         : view === "chart" ? <TeamReportChart rows={rows} metric={metric} onMetricChange={setMetric}
            chartType={chartType} onChartTypeChange={setChartType} />
        : <div className="admin-report-table" role="region" aria-label="Report table" tabIndex={0}>
          <table>
            <thead><tr><th scope="col">ASHA Worker</th>{columns.map(([key, label]) => <th key={key} scope="col">{label}</th>)}</tr></thead>
            <tbody>
              {rows.map(row => <tr key={row.worker_id}>
                <th scope="row">{row.worker_name}</th>
                {columns.map(([key]) => <td key={key}>{row[key]}</td>)}
              </tr>)}
            </tbody>
            <tfoot><tr><th scope="row">Team total</th>
              {columns.map(([key]) => <td key={key}>{rows.reduce((total, row) => total + row[key], 0)}</td>)}
            </tr></tfoot>
          </table>
          </div>}
    </section>
  </>;
}
