import { useState, useRef } from "react";
import { uploadDocument, processDocument, checkLoanFile } from "../api";

export default function DocumentToolbar({ loanFileId, onDone }) {
    const [status, setStatus] = useState(""); // shows what's happening, since these calls take a few seconds (real LLM calls)
    const fileInputRef = useRef(null);

    async function handleFileSelected(e) {
        const file = e.target.files[0];
        if (!file) return;

        setStatus("Uploading...");
        const uploadResult = await uploadDocument(loanFileId, file);

        setStatus(
            "Processing (classify + extract, this calls the LLM, may take a few seconds)...",
        );
        await processDocument(uploadResult.document_id);

        setStatus("Done.");
        onDone(); // parent re-fetches register/review/findings/changelog
        e.target.value = ""; // reset the input so the same filename can be re-selected later if needed
    }

    async function handleCheck() {
        setStatus("Running playbook check...");
        await checkLoanFile(loanFileId);
        setStatus("Done.");
        onDone();
    }

    return (
        <div className="flex items-center gap-3 mb-4">
            <button
                onClick={() => fileInputRef.current.click()}
                className="border-2 border-ink px-3 py-1.5 font-mono text-xs bg-card hover:bg-ink hover:text-card"
            >
                Upload Document
            </button>
            <input
                ref={fileInputRef}
                type="file"
                accept=".txt"
                onChange={handleFileSelected}
                className="hidden"
            />

            <button
                onClick={handleCheck}
                className="border-2 border-ink-blue text-ink-blue px-3 py-1.5 font-mono text-xs hover:bg-ink-blue hover:text-card"
            >
                Run Playbook Check
            </button>

            {status && (
                <span className="font-mono text-xs text-ink/60">{status}</span>
            )}
        </div>
    );
}
