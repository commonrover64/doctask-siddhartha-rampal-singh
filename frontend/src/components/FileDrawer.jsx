import { useState } from "react";
import { createLoanFile } from "../api";

export default function FileDrawer({
    loanFiles,
    selectedId,
    onSelect,
    onCreated,
}) {
    const [newName, setNewName] = useState("");
    const [creating, setCreating] = useState(false);

    async function handleCreate() {
        if (!newName.trim()) return;
        setCreating(true);
        await createLoanFile(newName.trim());
        setNewName("");
        setCreating(false);
        onCreated(); // parent re-fetches the loan file list
    }

    return (
        <div className="w-56 shrink-0">
            <h2 className="font-heading text-sm uppercase tracking-widest mb-3">
                File Drawer
            </h2>

            <div className="flex flex-col gap-2 mb-4">
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

            <div className="border-t-2 border-ink pt-3 flex flex-col gap-2">
                <input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="Borrower name"
                    className="border-2 border-ink px-2 py-1 font-mono text-sm bg-card"
                />
                <button
                    onClick={handleCreate}
                    disabled={creating}
                    className="border-2 border-ink-blue text-ink-blue px-2 py-1 font-mono text-xs hover:bg-ink-blue hover:text-card"
                >
                    {creating ? "Creating..." : "+ New File"}
                </button>
            </div>
        </div>
    );
}
