import React, { useState } from "react";

export default function CreateRecord({ onAdd }) {
  const [restaurantName, setRestaurantName] = useState("");
  const [cuisine, setCuisine] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    await onAdd({ restaurantName, cuisine });
  }

  return (
    <div className="card">
      <h3>Add record</h3>
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
        <button type="submit">Add record</button>
      </form>
    </div>
  );
}
