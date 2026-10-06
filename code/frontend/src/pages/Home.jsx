import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";
import {
  PAGE_SIZE,
  deleteInspection,
  fetchInspections,
} from "../features/inspectionsSlice.js";

export default function Home({ onLogout }) {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { items, skip, hasMore, status, error } = useSelector((state) => state.inspections);

  useEffect(() => {
    if (status === "idle") {
      dispatch(fetchInspections({ skip: 0 }));
    }
  }, [status, dispatch]);

  function handleDelete(record) {
    if (window.confirm(`Delete ${record.inspectionCode} (${record.restaurantName})?`)) {
      dispatch(deleteInspection(record.id));
    }
  }

  function goToPage(newSkip) {
    dispatch(fetchInspections({ skip: newSkip }));
  }

  return (
    <div className="card">
      <div className="card-top">
        <h3>Records</h3>
        <button className="secondary" onClick={onLogout}>
          Log out
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {status === "loading" ? (
        <p className="status">Loading records…</p>
      ) : items.length === 0 ? (
        <p className="status">No inspection records yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="record-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Code</th>
                <th>Restaurant name</th>
                <th>Cuisine</th>
                <th>Score</th>
                <th>Owner ID</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((record) => (
                <tr key={record.id}>
                  <td>{record.id}</td>
                  <td className="nowrap">{record.inspectionCode}</td>
                  <td>{record.restaurantName}</td>
                  <td>{record.cuisine}</td>
                  <td>{record.score}</td>
                  <td>{record.ownerId}</td>
                  <td>
                    <div className="actions">
                      <button onClick={() => navigate(`/update/${record.id}`)}>Update</button>
                      <button className="danger" onClick={() => handleDelete(record)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pager">
        <button
          className="secondary"
          disabled={skip === 0 || status === "loading"}
          onClick={() => goToPage(Math.max(0, skip - PAGE_SIZE))}
        >
          Previous
        </button>
        <span>
          Rows {skip + 1}–{skip + PAGE_SIZE}
        </span>
        <button
          className="secondary"
          disabled={!hasMore || status === "loading"}
          onClick={() => goToPage(skip + PAGE_SIZE)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
