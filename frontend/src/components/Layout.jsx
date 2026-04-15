import { useEffect, useState } from "react";
import { api } from "../api";

export function Layout({ children }) {
  const [user, setUser] = useState(null);

  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null));
  }, []);

  const logout = () => {
    localStorage.removeItem("token");
    window.location.href = "/login";
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-indigo-600 rounded-md" />
            <h1 className="text-lg font-semibold text-gray-900">Employee Clearance Portal</h1>
          </div>
          {user && (
            <div className="flex items-center gap-4 text-sm text-gray-600">
              <span>
                {user.email} · <span className="font-medium text-gray-900">{user.department}</span>
              </span>
              <button
                onClick={logout}
                className="px-3 py-1.5 rounded-md border border-gray-300 hover:bg-gray-100"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
