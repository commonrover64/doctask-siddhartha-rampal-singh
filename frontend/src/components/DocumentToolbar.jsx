import { useState, useRef, useEffect } from "react";
import {
    uploadDocument,
    processDocument,
    checkLoanFile,
    listDocuments,
} from "../api";

export default function DocumentToolbar({ loanFileId, onDone }) {
    const [fileStatuses, setFileStatuses] = useState([]);
    const [checking, setChecking] = useState(false);
    const [documents, setDocuments] = useState([]);
    const fileInputRef = useRef(null);

    useEffect(() => {
        refreshDocuments();
    }, [loanFileId]);

    function refreshDocuments() {
        listDocuments(loanFileId).then(setDocuments);
    }

    function updateStatus(name, status, autoVanish = false) {
        setFileStatuses((prev) => [
            ...prev.filter((f) => f.name !== name),
            { name, status },
        ]);
        if (autoVanish) {
            setTimeout(() => {
                setFileStatuses((prev) => prev.filter((f) => f.name !== name));
            }, 4000); // done/error messages clear themselves, in-progress ones don't
        }
    }

    async function processOne(documentId, label) {
        try {
            updateStatus(label, "processing (LLM call, a few seconds)");
            await processDocument(documentId);
            updateStatus(label, "done", true);
        } catch (err) {
            updateStatus(label, `error: ${err.message}`, true);
        }
    }

    async function handleFilesSelected(e) {
        const files = Array.from(e.target.files);
        e.target.value = "";

        for (const file of files) {
            try {
                updateStatus(file.name, "uploading");
                const result = await uploadDocument(loanFileId, file);

                if (result.error) {
                    updateStatus(file.name, `error: ${result.error}`, true);
                    continue;
                }
                if (result.duplicate && result.already_processed) {
                    updateStatus(
                        file.name,
                        "already uploaded and processed, skipped",
                        true,
                    );
                    continue;
                }
                // either brand new, or duplicate content that was never processed, either way, process it now
                await processOne(result.document_id, file.name);
            } catch (err) {
                updateStatus(file.name, `error: ${err.message}`, true);
            }
        }

        refreshDocuments();
        onDone();
    }

    async function handleResumeUnprocessed() {
        const unprocessed = documents.filter((d) => !d.doc_type);
        for (const doc of unprocessed) {
            await processOne(doc.document_id, doc.file_path);
        }
        refreshDocuments();
        onDone();
    }

    async function handleCheck() {
        setChecking(true);
        try {
            await checkLoanFile(loanFileId);
        } finally {
            setChecking(false);
        }
        onDone();
    }

    const unprocessedCount = documents.filter((d) => !d.doc_type).length;

    return (
        <div className="mb-4">
            {unprocessedCount > 0 && (
                <div className="border-2 border-stamp-amber bg-stamp-amber/10 px-3 py-2 mb-3 flex items-center justify-between">
                    <span className="font-mono text-sm text-stamp-amber">
                        {unprocessedCount} document
                        {unprocessedCount > 1 ? "s" : ""} uploaded but not yet
                        processed
                    </span>
                    <button
                        onClick={handleResumeUnprocessed}
                        className="border-2 border-stamp-amber text-stamp-amber px-3 py-1 font-mono text-sm hover:bg-stamp-amber hover:text-card"
                    >
                        Resume Processing
                    </button>
                </div>
            )}

            <div className="flex items-center gap-3">
                <button
                    onClick={() => fileInputRef.current.click()}
                    className="border-2 border-ink px-3 py-1.5 font-mono text-sm bg-card hover:bg-ink hover:text-card"
                >
                    Upload Document(s)
                </button>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt"
                    multiple
                    onChange={handleFilesSelected}
                    className="hidden"
                />

                <button
                    onClick={handleCheck}
                    disabled={checking}
                    className="border-2 border-ink-blue text-ink-blue px-3 py-1.5 font-mono text-sm hover:bg-ink-blue hover:text-card disabled:opacity-50"
                >
                    {checking ? "Checking..." : "Run Playbook Check"}
                </button>
            </div>

            {fileStatuses.length > 0 && (
                <div className="mt-2 flex flex-col gap-1">
                    {fileStatuses.map((f) => (
                        <span
                            key={f.name}
                            className={`font-mono text-sm ${f.status.startsWith("error") ? "text-stamp-red" : "text-ink/60"}`}
                        >
                            {f.name}: {f.status}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}
