import { useEffect, useState } from "react";
import { api } from "../api";

export function ProtectedRoute({ children }) {
  const [checking, setChecking] = useState(true);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    api
      .me()
      .then(() => {
        setOk(true);
        setChecking(false);
      })
      .catch(() => {
        setOk(false);
        setChecking(false);
        window.location.href = "/login";
      });
  }, []);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-600">
        Loading...
      </div>
    );
  }

  return ok ? children : null;
}
