import { useState } from "react";
import { api } from "../api";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const data = await api.login(email, password);
      localStorage.setItem("token", data.access_token);
      window.location.href = "/";
    } catch (err) {
      setError(err.message || "Login failed");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 px-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow p-8">
        <h2 className="text-2xl font-semibold text-gray-900 mb-6">Sign in</h2>
        {error && <div className="mb-4 text-red-600 text-sm">{error}</div>}
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Password</label>
            <input
              type="password"
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-md bg-indigo-600 text-white py-2 font-medium hover:bg-indigo-700"
          >
            Sign in
          </button>
        </form>
        <div className="mt-6 text-xs text-gray-500">
          <p className="font-medium mb-1">Demo accounts:</p>
          <div className="space-y-0.5">
            <p>hr_telecom@ecp.com / password</p>
            <p>hr_group@ecp.com / password</p>
            <p>it@ecp.com / password</p>
            <p>accounts@ecp.com / password</p>
            <p>audit@ecp.com / password</p>
            <p>finance@ecp.com / password</p>
          </div>
        </div>
      </div>
    </div>
  );
}
