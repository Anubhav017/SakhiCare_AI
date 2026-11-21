import { useState, type FormEvent } from "react";
import { uploadPatientReport, type Patient } from "./records";

export function PatientReportUpload({ patients }: { patients: Patient[] }) {
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const patientId = String(data.get("patient") ?? "");
    const file = data.get("report");
    if (saving || !patientId || !(file instanceof File) || !file.size) return;
    setError("");
    setMessage("");
    setSaving(true);
    try {
      await uploadPatientReport(patientId, file);
      form.reset();
      setMessage("Patient report saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not upload the report.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <header className="page-head"><h1 id="field-page-heading" tabIndex={-1}>Upload patient report</h1></header>
      <section className="panel">
        {patients.length ? (
          <form onSubmit={submit}>
            <label>Patient
              <select name="patient" defaultValue="" required disabled={saving}>
                <option value="" disabled>Select a patient</option>
                {patients.map(patient => <option key={patient.id} value={patient.id}>{patient.name}</option>)}
              </select>
            </label>
            <label>PDF report (up to 10 MB)
              <input name="report" type="file" accept=".pdf,application/pdf" required disabled={saving} />
            </label>
            {error && <p role="alert">{error}</p>}
            {message && <p role="status">{message}</p>}
            <button className="btn" type="submit" disabled={saving}>{saving ? "Uploading..." : "Upload PDF"}</button>
          </form>
        ) : <p>No patients available. <a href="#patients">Go to Patients</a></p>}
      </section>
    </>
  );
}
