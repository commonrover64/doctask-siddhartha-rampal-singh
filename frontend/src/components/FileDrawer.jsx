import { useState, useEffect } from "react";
import { createLoanFile } from "../api";

const PAGE_SIZE = 10;

export default function FileDrawer({
    loanFiles,
    selectedId,
    onSelect,
    onCreated,
}) {
    const [search, setSearch] = useState("");
    const [page, setPage] = useState(1);
    const [showCreate, setShowCreate] = useState(false);
    const [newName, setNewName] = useState("");
    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState("");

    const filtered = loanFiles.filter((lf) =>
        lf.borrower_name.toLowerCase().includes(search.toLowerCase()),
    );
    const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
    const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    useEffect(() => {
        setPage(1); // jump back to page 1 whenever the search term changes, avoids landing on an empty page
    }, [search]);

    async function handleCreate() {
        if (!newName.trim()) {
            setCreateError("Enter a borrower name first.");
            return;
        }
        setCreateError("");
        setCreating(true);
        await createLoanFile(newName.trim());
        setNewName("");
        setCreating(false);
        setShowCreate(false);
        onCreated();
    }

    return (
        <div className="w-56 shrink-0">
            <h2 className="font-heading text-base uppercase tracking-widest mb-3">
                File Drawer
            </h2>

            <div className="flex gap-1 mb-3">
                <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search..."
                    className="border-2 border-ink px-2 py-1 font-mono text-sm bg-card flex-1"
                />
                <button
                    onClick={() => setShowCreate((s) => !s)}
                    className="border-2 border-ink-blue text-ink-blue px-2 font-mono text-sm hover:bg-ink-blue hover:text-card"
                    title="Add new loan file"
                >
                    +
                </button>
            </div>

            {showCreate && (
                <div className="border-2 border-ink bg-card p-2 mb-3 flex flex-col gap-2">
                    <input
                        value={newName}
                        onChange={(e) => {
                            setNewName(e.target.value);
                            setCreateError("");
                        }}
                        onKeyDown={(e)=>{
                            if (e.key === "Enter" && !creating) {
                                handleCreate()
                            }
                        }}
                        placeholder="Borrower name"
                        className="border-2 border-ink px-2 py-1 font-mono text-sm"
                        autoFocus
                    />
                    {createError && (
                        <p className="font-mono text-sm text-stamp-red">
                            {createError}
                        </p>
                    )}
                    <button
                        onClick={handleCreate}
                        disabled={creating}
                        className="border-2 border-stamp-green text-stamp-green px-2 py-1 font-mono text-sm hover:bg-stamp-green hover:text-card"
                    >
                        {creating ? "Creating..." : "Create"}
                    </button>
                </div>
            )}

            <div className="flex flex-col gap-2 mb-2">
                {pageItems.length === 0 && (
                    <p className="font-body text-sm text-ink/50">No matches.</p>
                )}
                {pageItems.map((lf) => (
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

            {filtered.length > PAGE_SIZE && (
                <div className="flex items-center justify-between font-mono text-sm text-ink/60">
                    <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="border-2 border-ink px-2 disabled:opacity-30"
                    >
                        ‹
                    </button>
                    <span>
                        Page {page} of {totalPages}
                    </span>
                    <button
                        onClick={() =>
                            setPage((p) => Math.min(totalPages, p + 1))
                        }
                        disabled={page === totalPages}
                        className="border-2 border-ink px-2 disabled:opacity-30"
                    >
                        ›
                    </button>
                </div>
            )}
        </div>
    );
}
