import React, { useEffect, useState } from "react";
import { Link, Route, Routes, useNavigate } from "react-router-dom";
import Login from "./pages/Login.jsx";
import Home from "./pages/Home.jsx";
import CreateRecord from "./pages/CreateRecord.jsx";
import UpdateRecord from "./pages/UpdateRecord.jsx";
import DeleteRecord from "./pages/DeleteRecord.jsx";
import {
  createInspection,
  deleteInspection,
  fetchInspections,
  login,
  logout,
  me,
  onSessionExpired,
  updateInspection,
} from "./api/inspectionsApi.js";

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
  const [auth, setAuth] = useState({ loggedIn: false, userId: null });
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const data = await me();
        setAuth({ loggedIn: true, userId: data.userId });
      } catch {
        setAuth({ loggedIn: false, userId: null });
      }
    })();
  }, []);

  useEffect(() => {
    return onSessionExpired(() => {
      setAuth({ loggedIn: false, userId: null });
      setRecords([]);
      alert("Session expired. Please log in again.");
      navigate("/login");
    });
  }, [navigate]);

  useEffect(() => {
    (async () => {
      if (!auth.loggedIn) {
        setRecords([]);
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const data = await fetchInspections();
        setRecords(data);
      } catch (err) {
        console.error(err);
        setRecords([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [auth.loggedIn]);

  async function onLogin(email, password) {
    try {
      const data = await login(email, password);
      setAuth({ loggedIn: true, userId: data.userId });
      navigate("/");
      return true;
    } catch (err) {
      console.error(err);
      alert("Login failed. Check email and password.");
      return false;
    }
  }

  async function onLogout() {
    try {
      await logout();
    } finally {
      setAuth({ loggedIn: false, userId: null });
      setRecords([]);
      navigate("/login");
    }
  }

  async function onAdd(newRecord) {
    const created = await createInspection(newRecord);
    setRecords((prev) => [...prev, created]);
    navigate("/");
  }

  async function onUpdate(id, updatedRecord) {
    const updated = await updateInspection(id, updatedRecord);
    setRecords((prev) => prev.map((record) => (record.id === id ? updated : record)));
    navigate("/");
  }

  async function onDelete(id) {
    await deleteInspection(id);
    setRecords((prev) => prev.filter((record) => record.id !== id));
    navigate("/");
  }

  return (
    <>
      <header className="heading">
        <Link className="heading-title" to="/">
          Restaurant Inspections
        </Link>
        <nav className="heading-links">
          <Link to="/">Home</Link>
          {auth.loggedIn ? <Link to="/create">Add record</Link> : <Link to="/login">Log in</Link>}
        </nav>
      </header>
      <div className={auth.loggedIn ? "page wide" : "page"}> 
        <Routes>
          <Route
            path="/"
            element={
              <RequireAuth auth={auth}>
                <Home records={records} loading={loading} onLogout={onLogout} />
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
                <CreateRecord onAdd={onAdd} />
              </RequireAuth>
            }
          />
          <Route
            path="/update/:id"
            element={
              <RequireAuth auth={auth}>
                <UpdateRecord records={records} onUpdate={onUpdate} />
              </RequireAuth>
            }
          />
          <Route
            path="/delete/:id"
            element={
              <RequireAuth auth={auth}>
                <DeleteRecord records={records} onDelete={onDelete} />
              </RequireAuth>
            }
          />
        </Routes>
      </div>
    </>
  );
}
