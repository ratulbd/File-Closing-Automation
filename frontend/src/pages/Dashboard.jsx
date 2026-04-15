import { useEffect, useState } from "react";
import { api } from "../api";
import { StatusBadge } from "../components/StatusBadge";

export function Dashboard() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [user, setUser] = useState(null);
  const [rejectModal, setRejectModal] = useState(null);
  const [rejectReason, setRejectReason] = useState("");
  const [forwardModal, setForwardModal] = useState(null);
  const [itRequired, setItRequired] = useState(true);
  const [forwardNotes, setForwardNotes] = useState("");

  useEffect(() => {
    api.me().then(setUser).catch(() => {});
    loadDashboard();
  }, []);

  const loadDashboard = () => {
    setLoading(true);
    api
      .getDashboard()
      .then((data) => {
        setItems(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  };

  const acknowledge = async (id) => {
    await api.acknowledge(id);
    loadDashboard();
  };

  const forward = async () => {
    const payload = {};
    if (forwardModal.current_department === "HR_GROUP" && forwardModal.current_phase === 1) {
      payload.it_required = itRequired;
    }
    if (forwardNotes.trim()) payload.notes = forwardNotes.trim();
    await api.forward(forwardModal.id, payload);
    setForwardModal(null);
    setForwardNotes("");
    loadDashboard();
  };

  const reject = async () => {
    if (!rejectReason.trim()) return;
    await api.reject(rejectModal.id, {
      reason: rejectReason.trim(),
      target_department: rejectModal.targetDepartment,
    });
    setRejectModal(null);
    setRejectReason("");
    loadDashboard();
  };

  const canCreate = user?.role === "HR_TELECOM";

  if (loading) return <div className="text-gray-600">Loading dashboard...</div>;
  if (error) return <div className="text-red-600">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">My Queue</h2>
        {canCreate && (
          <a
            href="/new"
            className="inline-flex items-center rounded-md bg-indigo-600 text-white px-4 py-2 text-sm font-medium hover:bg-indigo-700"
          >
            + New Clearance File
          </a>
        )}
      </div>

      {items.length === 0 ? (
        <div className="text-gray-500">No files in your queue.</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-gray-700">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Employee</th>
                <th className="px-4 py-3 text-left font-medium">Phase</th>
                <th className="px-4 py-3 text-left font-medium">SLA Status</th>
                <th className="px-4 py-3 text-left font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {items.map((item) => (
                <tr key={item.id}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{item.employee_name}</div>
                    <div className="text-gray-500">{item.employee_id}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-gray-900">Phase {item.current_phase}</div>
                    <div className="text-gray-500">{item.current_department}</div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={item.step_status} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {item.step_status === "PENDING" && (
                        <button
                          onClick={() => acknowledge(item.id)}
                          className="rounded-md bg-green-600 text-white px-3 py-1.5 text-xs font-medium hover:bg-green-700"
                        >
                          Acknowledge
                        </button>
                      )}
                      {item.step_status !== "PENDING" && (
                        <button
                          onClick={() => {
                            setItRequired(true);
                            setForwardNotes("");
                            setForwardModal(item);
                          }}
                          className="rounded-md bg-indigo-600 text-white px-3 py-1.5 text-xs font-medium hover:bg-indigo-700"
                        >
                          Forward
                        </button>
                      )}
                      <button
                        onClick={() => setRejectModal({ ...item, targetDepartment: item.current_department })}
                        className="rounded-md bg-red-600 text-white px-3 py-1.5 text-xs font-medium hover:bg-red-700"
                      >
                        Reject
                      </button>
                      <a
                        href={`/files/${item.id}`}
                        className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                      >
                        View
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {forwardModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow">
            <h3 className="text-lg font-semibold text-gray-900">Forward File</h3>
            <p className="text-sm text-gray-600 mt-1">
              {forwardModal.employee_name} ({forwardModal.employee_id})
            </p>

            {forwardModal.current_department === "HR_GROUP" && forwardModal.current_phase === 1 && (
              <label className="mt-4 flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={itRequired}
                  onChange={(e) => setItRequired(e.target.checked)}
                  className="h-4 w-4"
                />
                <span>IT Clearance Required</span>
              </label>
            )}

            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700">Notes (optional)</label>
              <textarea
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                rows={3}
                value={forwardNotes}
                onChange={(e) => setForwardNotes(e.target.value)}
              />
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setForwardModal(null)}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={forward}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
              >
                Confirm Forward
              </button>
            </div>
          </div>
        </div>
      )}

      {rejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow">
            <h3 className="text-lg font-semibold text-gray-900">Reject File</h3>
            <p className="text-sm text-gray-600 mt-1">
              {rejectModal.employee_name} ({rejectModal.employee_id})
            </p>
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700">
                Rejection Reason <span className="text-red-600">*</span>
              </label>
              <textarea
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                rows={3}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                required
              />
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setRejectModal(null)}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={reject}
                disabled={!rejectReason.trim()}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                Confirm Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
