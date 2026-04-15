import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { StatusBadge } from "../components/StatusBadge";

export function FileDetail() {
  const { id } = useParams();
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getFile(id)
      .then(setFile)
      .catch((err) => setError(err.message));
  }, [id]);

  if (error) return <div className="text-red-600">{error}</div>;
  if (!file) return <div className="text-gray-600">Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">File Details</h2>
        <a href="/" className="text-sm text-gray-600 hover:underline">
          ← Back to Dashboard
        </a>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide">Employee</div>
            <div className="text-lg font-medium text-gray-900">{file.employee_name}</div>
            <div className="text-sm text-gray-600">{file.employee_id}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide">Current Status</div>
            <div className="text-lg font-medium text-gray-900">{file.status}</div>
            <div className="text-sm text-gray-600">
              Phase {file.current_phase} · {file.current_department}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wide">IT Required</div>
            <div className="text-lg font-medium text-gray-900">
              {file.it_required ? "Yes" : "No"}
            </div>
            <div className="text-sm text-gray-600">
              Created {new Date(file.created_at).toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Timeline</h3>
        <div className="space-y-4">
          {file.steps.map((step, idx) => (
            <div key={step.id} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div
                  className={`w-3 h-3 rounded-full ${
                    step.status === "COMPLETED"
                      ? "bg-blue-600"
                      : step.status === "PENDING"
                      ? "bg-gray-300"
                      : "bg-indigo-600"
                  }`}
                />
                {idx < file.steps.length - 1 && (
                  <div className="w-0.5 flex-1 bg-gray-200 my-1" />
                )}
              </div>
              <div className="flex-1 pb-4">
                <div className="flex items-center justify-between">
                  <div className="font-medium text-gray-900">
                    Phase {step.phase} · {step.department}
                  </div>
                  <StatusBadge status={step.status} />
                </div>
                <div className="text-sm text-gray-600 mt-1">
                  SLA: {step.sla_hours > 0 ? `${step.sla_hours} hours` : "No limit"}
                </div>
                {step.acknowledged_at && (
                  <div className="text-sm text-gray-500">
                    Acknowledged: {new Date(step.acknowledged_at).toLocaleString()}
                  </div>
                )}
                {step.completed_at && (
                  <div className="text-sm text-gray-500">
                    Completed: {new Date(step.completed_at).toLocaleString()}
                  </div>
                )}
                {step.notes && (
                  <div className="mt-2 text-sm text-gray-700 bg-gray-50 rounded-md px-3 py-2">
                    <span className="font-medium">Notes:</span> {step.notes}
                  </div>
                )}
                {step.rejections?.length > 0 && (
                  <div className="mt-2 space-y-2">
                    {step.rejections.map((r) => (
                      <div
                        key={r.id}
                        className="text-sm text-red-700 bg-red-50 rounded-md px-3 py-2"
                      >
                        <span className="font-medium">Rejection:</span> {r.reason} (
                        <span className="text-red-800">
                          by {r.rejected_by} to {r.rejected_to}
                        </span>
                        )
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
