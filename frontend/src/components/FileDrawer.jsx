export default function FileDrawer({ loanFiles, selectedId, onSelect }) {
    return (
        <div className="w-56 shrink-0">
            <h2 className="font-heading text-sm uppercase tracking-widest mb-3">
                File Drawer
            </h2>
            <div className="flex flex-col gap-2">
                {loanFiles.map((lf) => (
                    <button
                        key={lf.loan_file_id}
                        onClick={() => onSelect(lf.loan_file_id)}
                        className={`text-left px-3 py-2 border-2 border-ink font-mono text-sm shadow-carbon-tight
              ${selectedId === lf.loan_file_id ? "bg-stamp-amber/20" : "bg-card"}`}
                    >
                        {lf.borrower_name}
                    </button>
                ))}
            </div>
        </div>
    );
}
