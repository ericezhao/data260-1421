import React from "react";
import { useNavigate } from "react-router-dom";

export default function Home({ records, loading, onLogout }) {
  const navigate = useNavigate();

  return (
    <div className="card">
      <div className="card-top">
        <h3>Records</h3>
        <button className="secondary" onClick={onLogout}>
          Log out
        </button>
      </div>

      {loading ? (
        <p className="status">Loading records…</p>
      ) : records.length === 0 ? (
        <p className="status">No inspection records yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="record-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Restaurant name</th>
                <th>Cuisine</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id}>
                  <td>{record.id}</td>
                  <td>{record.restaurantName}</td>
                  <td>{record.cuisine}</td>
                  <td className="actions">
                    <button onClick={() => navigate(`/update/${record.id}`)}>Update</button>
                    <button className="danger" onClick={() => navigate(`/delete/${record.id}`)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
