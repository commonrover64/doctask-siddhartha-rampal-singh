const STAMP_STYLES = {
  clean: "border-stamp-green text-stamp-green",
  approved: "border-stamp-green text-stamp-green",
  violation: "border-stamp-red text-stamp-red",
  rejected: "border-stamp-red text-stamp-red",
  pending: "border-stamp-amber text-stamp-amber",
  inconclusive: "border-stamp-amber text-stamp-amber",
  superseded: "border-stamp-gray text-stamp-gray line-through",
};

export default function StatusStamp({ status }) {
  const style = STAMP_STYLES[status] ?? "border-ink text-ink";
  return (
    <span
      className={`inline-block border-2 px-2 py-0.5 text-xs font-heading uppercase tracking-widest opacity-85 -rotate-3 ${style}`}
    >
      {status}
    </span>
  );
}