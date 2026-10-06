import React, { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate, useParams } from "react-router-dom";
import OwnerSelect from "../components/OwnerSelect.jsx";
import { errorMessage, fetchInspectionById } from "../api/inspectionsApi.js";
import { updateInspection } from "../features/inspectionsSlice.js";

const FIELDS = ["restaurantName", "cuisine", "inspectionCode", "score", "ownerId"];

export default function UpdateRecord() {
  const { id } = useParams();
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const items = useSelector((state) => state.inspections.items);

  const [idInput, setIdInput] = useState(id || "");
  const [original, setOriginal] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState(null);

  async function loadRecord(recordId) {
    setError(null);
    const fromStore = items.find((item) => item.id === Number(recordId));
    try {
      const record = fromStore || (await fetchInspectionById(recordId));
      setOriginal(record);
      setForm(Object.fromEntries(FIELDS.map((f) => [f, record[f]])));
    } catch (err) {
      setOriginal(null);
      setForm(null);
      setError(errorMessage(err));
    }
  }

  useEffect(() => {
    if (id) {
      loadRecord(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function update(field) {
    return (e) => setForm({ ...form, [field]: e.target.value });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    const changes = {};
    for (const field of FIELDS) {
      const value = field === "score" || field === "ownerId" ? Number(form[field]) : form[field];
      if (value !== original[field]) {
        changes[field] = value;
      }
    }
    if (Object.keys(changes).length === 0) {
      setError("Nothing changed.");
      return;
    }
    try {
      await dispatch(updateInspection({ id: original.id, changes })).unwrap();
      navigate("/");
    } catch (message) {
      setError(message);
    }
  }

  return (
    <div className="card">
      <h3>Update record</h3>
      {error && <p className="error">{error}</p>}

      <form
        className="id-picker"
        onSubmit={(e) => {
          e.preventDefault();
          loadRecord(idInput);
        }}
      >
        <label>
          Record ID
          <input
            type="number"
            min="1"
            value={idInput}
            onChange={(e) => setIdInput(e.target.value)}
            required
          />
        </label>
        <button type="submit" className="secondary">
          Load
        </button>
      </form>

      {form && (
        <form onSubmit={handleSubmit}>
          <label>
            Restaurant name
            <input value={form.restaurantName} onChange={update("restaurantName")} required />
          </label>
          <label>
            Cuisine
            <input value={form.cuisine} onChange={update("cuisine")} required />
          </label>
          <label>
            Inspection code
            <input value={form.inspectionCode} onChange={update("inspectionCode")} required />
          </label>
          <label>
            Score (0–100)
            <input type="number" value={form.score} onChange={update("score")} required />
          </label>
          <label>
            Owner
            <OwnerSelect value={form.ownerId} onChange={update("ownerId")} required />
          </label>
          <button type="submit">Update record {original.inspectionCode}</button>
        </form>
      )}
    </div>
  );
}
