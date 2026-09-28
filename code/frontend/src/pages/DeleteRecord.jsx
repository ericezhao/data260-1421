import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchInspectionById } from "../api/inspectionsApi.js";

export default function DeleteRecord({ records, onDelete }) {
  const { id } = useParams();
  const recordId = Number(id);
  const fromList = records.find((item) => item.id === recordId);

  const [record, setRecord] = useState(fromList || null);
  const [notFound, setNotFound] = useState(false);

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

  async function handleDelete() {
    await onDelete(recordId);
  }

  if (notFound) {
    return (
      <div className="card">
        <h3>Delete record</h3>
        <p>Record not found.</p>
        <Link to="/">Home</Link>
      </div>
    );
  }

  if (!record) {
    return (
      <div className="card">
        <h3>Delete record</h3>
        <p className="status">Loading record…</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h3>Delete record</h3>
      <p>
        Are you sure you want to delete <strong>{record.restaurantName}</strong> (
        {record.cuisine})?
      </p>
      <button className="danger" onClick={handleDelete}>
        Delete record
      </button>
    </div>
  );
}
