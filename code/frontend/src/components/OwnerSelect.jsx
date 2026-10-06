import React, { useEffect, useState } from "react";
import { fetchOwners } from "../api/inspectionsApi.js";

export default function OwnerSelect({ value, onChange, required = false }) {
  const [owners, setOwners] = useState([]);

  useEffect(() => {
    fetchOwners()
      .then(setOwners)
      .catch(() => setOwners([]));
  }, []);

  return (
    <select value={value} onChange={onChange} required={required}>
      <option value="">Select an owner</option>
      {owners.map((owner) => (
        <option key={owner.id} value={owner.id}>
          {owner.id} – {owner.name}
        </option>
      ))}
    </select>
  );
}
