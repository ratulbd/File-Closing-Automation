import { useEffect, useState } from "react";
import { api } from "../api";

export function ProtectedRoute({ children }) {
  const [checking, setChecking] = useState(true);
  const [ok, setOk] = useState(false);

  useEffect(() => {
    let timeoutId;

    const checkAuth = async () => {
      try {
        await api.me();
        setOk(true);
      } catch {
        setOk(false);
        window.location.href = "/login";
      } finally {
        setChecking(false);
      }
    };

    // Timeout safety: if backend is cold/slow, redirect after 8s
    timeoutId = setTimeout(() => {
      if (checking) {
        setChecking(false);
        setOk(false);
        window.location.href = "/login";
      }
    }, 8000);

    checkAuth();

    return () => clearTimeout(timeoutId);
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
