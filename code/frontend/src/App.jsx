import React, { useEffect, useState } from "react";
import { useDispatch } from "react-redux";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import Login from "./pages/Login.jsx";
import Home from "./pages/Home.jsx";
import CreateRecord from "./pages/CreateRecord.jsx";
import UpdateRecord from "./pages/UpdateRecord.jsx";
import { login, logout, me, onSessionExpired } from "./api/inspectionsApi.js";
import { resetInspections } from "./features/inspectionsSlice.js";

function RequireAuth({ auth, children }) {
  if (!auth.loggedIn) {
    return (
      <div className="card">
        <h3>Login required</h3>
        <p>Please log in to access this page.</p>
        <Link to="/login">Log in</Link>
      </div>
    );
  }
  return children;
}

export default function App() {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const [auth, setAuth] = useState({
    loggedIn: false,
    userId: null,
    username: null,
    role: null,
  });

  useEffect(() => {
    (async () => {
      try {
        const data = await me();
        setAuth({
          loggedIn: true,
          userId: data.id,
          username: data.username,
          role: data.role,
        });
      } catch {
        setAuth({ loggedIn: false, userId: null, username: null, role: null });
      }
    })();
  }, []);

  useEffect(() => {
    return onSessionExpired(() => {
      setAuth({ loggedIn: false, userId: null, username: null, role: null });
      dispatch(resetInspections());
      alert("Session expired. Please log in again.");
      navigate("/login");
    });
  }, [dispatch, navigate]);

  async function onLogin(username, password) {
    try {
      await login(username, password);
      const data = await me();
      setAuth({
        loggedIn: true,
        userId: data.id,
        username: data.username,
        role: data.role,
      });
      navigate("/");
      return true;
    } catch (err) {
      console.error(err);
      alert("Login failed. Check username and password.");
      return false;
    }
  }

  async function onLogout() {
    try {
      await logout();
    } finally {
      setAuth({ loggedIn: false, userId: null, username: null, role: null });
      dispatch(resetInspections());
      navigate("/login");
    }
  }

  return (
    <>
      <header className="heading">
        <Link className="heading-title" to="/">
          Restaurant Inspections
        </Link>
        <nav className="heading-links">
          <Link to="/">Home</Link>
          {auth.loggedIn ? (
            <>
              <Link to="/create">Add record</Link>
              <Link to="/update">Update record</Link>
            </>
          ) : (
            <Link to="/login">Log in</Link>
          )}
        </nav>
      </header>
      <div className={auth.loggedIn ? "page wide" : "page"}>
        <Routes>
          <Route
            path="/"
            element={
              <RequireAuth auth={auth}>
                <Home onLogout={onLogout} />
              </RequireAuth>
            }
          />
          <Route
            path="/login"
            element={<Login auth={auth} onLogin={onLogin} onLogout={onLogout} />}
          />
          <Route
            path="/create"
            element={
              <RequireAuth auth={auth}>
                <CreateRecord />
              </RequireAuth>
            }
          />
          <Route
            path="/update/:id?"
            element={
              <RequireAuth auth={auth}>
                <UpdateRecord />
              </RequireAuth>
            }
          />
        </Routes>
      </div>
    </>
  );
}
