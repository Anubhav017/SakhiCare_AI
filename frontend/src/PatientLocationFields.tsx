import { useEffect, useState } from "react";

const API = "https://api.dharun.dev/v1/lgd";
type Place = { code: number; name: string };

async function loadPlaces(path: string, signal: AbortSignal): Promise<Place[]> {
  const response = await fetch(`${API}/${path}`, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Location list could not be loaded.");
  const body = await response.json();
  if (!Array.isArray(body.data)) throw new Error("Location list is temporarily unavailable.");
  return body.data;
}

function LocationSelect({ label, name, value, places, disabled, onChange, placeholder }: {
  label: string; name: string; value: string; places: Place[]; disabled?: boolean;
  onChange: (value: string) => void; placeholder: string;
}) {
  return <label>{label}<select name={name} value={value} disabled={disabled} onChange={event => onChange(event.target.value)}>
    <option value="">{placeholder}</option>
    {places.map(place => <option key={place.code} value={place.code}>{place.name}</option>)}
  </select></label>;
}

export function PatientLocationFields() {
  const [states, setStates] = useState<Place[]>([]);
  const [districts, setDistricts] = useState<Place[]>([]);
  const [blocks, setBlocks] = useState<Place[]>([]);
  const [villages, setVillages] = useState<Place[]>([]);
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [block, setBlock] = useState("");
  const [areaType, setAreaType] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    loadPlaces("states", controller.signal).then(items => {
      const sorted = items.sort((a, b) => a.name.localeCompare(b.name));
      setStates(sorted);
      const bihar = sorted.find(item => item.name.toLowerCase() === "bihar");
      if (bihar) setState(String(bihar.code));
    })
      .catch(() => { if (!controller.signal.aborted) setError("Could not load states. Check your connection and retry."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retryCount]);

  useEffect(() => {
    setDistricts([]); setBlocks([]); setVillages([]); setDistrict(""); setBlock(""); setAreaType("");
    if (!state) return;
    const controller = new AbortController();
    setLoading(true); setError("");
    loadPlaces(`districts?state=${encodeURIComponent(state)}`, controller.signal)
      .then(items => setDistricts(items.sort((a, b) => a.name.localeCompare(b.name))))
      .catch(() => { if (!controller.signal.aborted) setError("Could not load districts for this state. Select it again to retry."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [state, retryCount]);

  useEffect(() => {
    setBlocks([]); setVillages([]); setBlock(""); setAreaType("");
    if (!district) return;
    const controller = new AbortController();
    setLoading(true); setError("");
    loadPlaces(`subdistricts?district=${encodeURIComponent(district)}`, controller.signal)
      .then(items => setBlocks(items.sort((a, b) => a.name.localeCompare(b.name))))
      .catch(() => { if (!controller.signal.aborted) setError("Could not load blocks for this district. Select it again to retry."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [district, retryCount]);

  useEffect(() => {
    setVillages([]);
    if (!block || areaType !== "village") return;
    const controller = new AbortController();
    setLoading(true); setError("");
    loadPlaces(`villages?subdistrict=${encodeURIComponent(block)}`, controller.signal)
      .then(items => setVillages(items.sort((a, b) => a.name.localeCompare(b.name))))
      .catch(() => { if (!controller.signal.aborted) setError("Could not load villages for this block. Select the block again to retry."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [block, areaType, retryCount]);

  return <section className="patient-location-fields" aria-label="Patient location">
    <h3>Location <small>Optional · helps organize your patient list</small></h3>
    <div className="patient-location-grid">
      <input type="hidden" name="state" value={states.find(item => String(item.code) === state)?.name ?? ""} />
    <input type="hidden" name="district" value={districts.find(item => String(item.code) === district)?.name ?? ""} />
    <input type="hidden" name="block" value={blocks.find(item => String(item.code) === block)?.name ?? ""} />
    <LocationSelect label="State" name="state_code" value={state} places={states} placeholder={loading && !states.length ? "Loading states…" : "Choose a state"} onChange={setState} />
      <LocationSelect label="District" name="district_code" value={district} places={districts} disabled={!state} placeholder={state ? "Choose a district" : "Select a state first"} onChange={setDistrict} />
      <LocationSelect label="Block / sub-district" name="block_code" value={block} places={blocks} disabled={!district} placeholder={district ? "Choose a block" : "Select a district first"} onChange={setBlock} />
      {district && <label>Area type<select name="locality_type" value={areaType} onChange={event => { setAreaType(event.target.value); setVillages([]); }}>
        <option value="">Choose village or urban ward</option><option value="village">Rural village</option><option value="ward">Urban ward</option>
      </select></label>}
      {areaType === "village" && <label>Village<select name="village" defaultValue="" disabled={!block}>
        <option value="">{!block ? "Select a block first" : loading ? "Loading villages…" : "Choose a village"}</option>
        {villages.map(place => <option key={place.code} value={place.name}>{place.name}</option>)}
      </select></label>}
      {areaType === "ward" && <>
        <label>Town / city<input name="town" maxLength={100} placeholder="Enter town or city" /></label>
        <label>Ward number<input name="ward" maxLength={30} placeholder="Enter ward number" /></label>
      </>}
    </div>
    <small className="location-attribution">Location directory: LGD India · Bihar is preselected; change State for another location.</small>
    {error && <p className="location-error" role="status">{error} <button type="button" className="location-retry" onClick={() => setRetryCount(count => count + 1)}>Retry</button></p>}
  </section>;
}


