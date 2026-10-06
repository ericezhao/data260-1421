import React, { useState } from "react";
import { useDispatch } from "react-redux";
import { useNavigate } from "react-router-dom";
import OwnerSelect from "../components/OwnerSelect.jsx";
import { createInspection } from "../features/inspectionsSlice.js";

export default function CreateRecord() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    restaurantName: "",
    cuisine: "",
    inspectionCode: "",
    score: 100,
    ownerId: "",
  });
  const [error, setError] = useState(null);

  function update(field) {
    return (e) => setForm({ ...form, [field]: e.target.value });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    try {
      await dispatch(
        createInspection({ ...form, score: Number(form.score), ownerId: Number(form.ownerId) })
      ).unwrap();
      navigate("/");
    } catch (message) {
      setError(message);
    }
  }

  return (
    <div className="card">
      <h3>Add record</h3>
      {error && <p className="error">{error}</p>}
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
          <input
            value={form.inspectionCode}
            onChange={update("inspectionCode")}
            placeholder="INS-12345"
            required
          />
        </label>
        <label>
          Score (0–100)
          <input type="number" value={form.score} onChange={update("score")} required />
        </label>
        <label>
          Owner
          <OwnerSelect value={form.ownerId} onChange={update("ownerId")} required />
        </label>
        <button type="submit">Add record</button>
      </form>
    </div>
  );
}
