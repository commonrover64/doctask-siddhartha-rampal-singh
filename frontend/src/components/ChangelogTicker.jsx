export default function ChangelogTicker({ entries }) {
  if (entries.length === 0) return <p className="font-body text-sm">No changes recorded yet.</p>;

  return (
    <div className="flex flex-col gap-2 border-l-2 border-ink pl-4">
      {entries.map((e) => (
        <div key={e.history_id} className="font-mono text-xs">
          <span className="text-ink/50">{new Date(e.changed_at).toLocaleString()}</span>
          {"  "}
          <span className="font-bold">{e.field_name}</span> changed
        </div>
      ))}
    </div>
  );
}