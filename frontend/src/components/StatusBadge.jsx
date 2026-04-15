export function StatusBadge({ status }) {
  const map = {
    ACKNOWLEDGED: { emoji: "🟢", label: "On Time", color: "text-green-600" },
    PENDING: { emoji: "⚪", label: "Pending", color: "text-gray-500" },
    NEAR_BREACH: { emoji: "🟡", label: "Near Breach", color: "text-yellow-600" },
    BREACHED: { emoji: "🔴", label: "SLA Breached", color: "text-red-600" },
    COMPLETED: { emoji: "✅", label: "Completed", color: "text-blue-600" },
  };
  const s = map[status] || { emoji: "⚪", label: status, color: "text-gray-500" };
  return (
    <span className={`inline-flex items-center gap-1 font-medium ${s.color}`}>
      <span>{s.emoji}</span>
      <span>{s.label}</span>
    </span>
  );
}
