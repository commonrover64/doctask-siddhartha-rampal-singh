export default function Sidebar({ loanFiles, selectedId, onSelect }) {
  return (
    <aside className="w-64 shrink-0 border-r border-surface1 overflow-y-auto">
      <h1 className="px-4 py-4 text-sm font-medium tracking-wide text-subtext0 uppercase">
        Loan Files
      </h1>
      <ul>
        {loanFiles.map((lf) => (
          <li key={lf.loan_file_id}>
            <button
              onClick={() => onSelect(lf.loan_file_id)}
              className={`w-full text-left px-4 py-3 border-l-2 transition-colors ${
                selectedId === lf.loan_file_id
                  ? "border-accent bg-surface0 text-text"
                  : "border-transparent text-subtext0 hover:bg-surface0 hover:text-text"
              }`}
            >
              {lf.borrower_name}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}