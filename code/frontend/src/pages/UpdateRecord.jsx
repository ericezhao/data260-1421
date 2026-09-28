import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchInspectionById } from "../api/inspectionsApi.js";

export default function UpdateRecord({ records, onUpdate }) {
  const { id } = useParams();
  const recordId = Number(id);
  const fromList = records.find((item) => item.id === recordId);

  const [record, setRecord] = useState(fromList || null);
  const [notFound, setNotFound] = useState(false);
  const [restaurantName, setRestaurantName] = useState("");
  const [cuisine, setCuisine] = useState("");

  useEffect(() => {
    if (fromList) {
      setRecord(fromList);
      setNotFound(false);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const data = await fetchInspectionById(recordId);
        if (!cancelled) {
          setRecord(data);
          setNotFound(false);
        }
      } catch {
        if (!cancelled) {
          setRecord(null);
          setNotFound(true);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [fromList, recordId]);

  useEffect(() => {
    if (!record) {
      return;
    }
    setRestaurantName(record.restaurantName);
    setCuisine(record.cuisine);
  }, [record]);

  async function handleSubmit(event) {
    event.preventDefault();
    await onUpdate(recordId, { restaurantName, cuisine });
  }

  if (notFound) {
    return (
      <div className="card">
        <h3>Update record</h3>
        <p>Record not found.</p>
        <Link to="/">Home</Link>
      </div>
    );
  }

  if (!record) {
    return (
      <div className="card">
        <h3>Update record</h3>
        <p className="status">Loading record…</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3>Update record (ID: {recordId})</h3>
      <form onSubmit={handleSubmit}>
        <label>
          Restaurant name
          <input
            value={restaurantName}
            onChange={(e) => setRestaurantName(e.target.value)}
            required
          />
        </label>
        <label>
          Cuisine
          <input value={cuisine} onChange={(e) => setCuisine(e.target.value)} required />
        </label>
        <button type="submit">Update record</button>
      </form>
    </div>
  );
}
