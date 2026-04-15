import { useState } from "react";
import { api } from "../api";

const DEPARTMENTS = [
  "HR_TELECOM",
  "HR_GROUP",
  "IT",
  "ACCOUNTS",
  "AUDIT",
  "FINANCE"
];

export function NewFile() {
  const [employeeId, setEmployeeId] = useState("");
  const [employeeName, setEmployeeName] = useState("");
  const [department, setDepartment] = useState("HR_TELECOM");
  const [clearanceReason, setClearanceReason] = useState("");
  const [itRequired, setItRequired] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      await api.createFile({
        employee_id: employeeId,
        employee_name: employeeName,
        department: department,
        clearance_reason: clearanceReason,
        it_required: itRequired
      });
      setSuccess("Clearance file created successfully.");
      setEmployeeId("");
      setEmployeeName("");
      setDepartment("HR_TELECOM");
      setClearanceReason("");
      setItRequired(false);
    } catch (err) {
      setError(err.message || "Failed to create file");
    }
  };

  return (
    <div className="max-w-xl">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Initiate Clearance File</h2>
      {success && <div className="mb-4 rounded-md bg-green-50 text-green-700 px-4 py-3">{success}</div>}
      {error && <div className="mb-4 rounded-md bg-red-50 text-red-700 px-4 py-3">{error}</div>}
      <form onSubmit={submit} className="space-y-4 bg-white rounded-xl border border-gray-200 p-6">
        <div>
          <label className="block text-sm font-medium text-gray-700">Employee ID</label>
          <input
            type="text"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={employeeId}
            onChange={(e) => setEmployeeId(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Employee Name</label>
          <input
            type="text"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={employeeName}
            onChange={(e) => setEmployeeName(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Department</label>
          <select
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            required
          >
            {DEPARTMENTS.map(dept => (
              <option key={dept} value={dept}>{dept}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Clearance Reason</label>
          <textarea
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={clearanceReason}
            onChange={(e) => setClearanceReason(e.target.value)}
            rows="3"
            required
          />
        </div>
        <div className="flex items-center">
          <input
            type="checkbox"
            id="itRequired"
            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            checked={itRequired}
            onChange={(e) => setItRequired(e.target.checked)}
          />
          <label htmlFor="itRequired" className="ml-2 block text-sm text-gray-700">
            IT Clearance Required
          </label>
        </div>
        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            className="rounded-md bg-indigo-600 text-white px-4 py-2 font-medium hover:bg-indigo-700"
          >
            Create File
          </button>
          <a href="/" className="text-sm text-gray-600 hover:underline">
            Back to Dashboard
          </a>
        </div>
      </form>
    </div>
  );
}
