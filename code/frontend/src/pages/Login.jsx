import React, { useState } from "react";

export default function Login({ auth, onLogin, onLogout }) {
  // state variables to store the email and password
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event) {
    // prevent the default behavior of the form - refreshing the page
    event.preventDefault();
    const success = await onLogin(email, password);
    if (success) {
      setEmail("");
      setPassword("");
    }
  }

  if (auth.loggedIn) {
    return (
      <div className="card">
        <h3>Login</h3>
        <p>You are logged in.</p>
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
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
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
