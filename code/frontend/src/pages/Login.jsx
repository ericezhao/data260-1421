import React, { useState } from "react";

export default function Login({ auth, onLogin, onLogout }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    const success = await onLogin(username, password);
    if (success) {
      setUsername("");
      setPassword("");
    }
  }

  if (auth.loggedIn) {
    return (
      <div className="card">
        <h3>Login</h3>
        <p>
          Logged in as {auth.username} ({auth.role}).
        </p>
        <button className="secondary" onClick={onLogout}>
          Log out
        </button>
      </div>
    );
  }

  return (
    <div className="card">
      <h3>Login</h3>
      <form onSubmit={handleSubmit}>
        <label>
          Username
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        <button type="submit">Log in</button>
      </form>
    </div>
  );
}
