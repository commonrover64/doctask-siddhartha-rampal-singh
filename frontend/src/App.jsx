import { useState, useEffect } from "react";
import {
    listLoanFiles,
    getRegister,
    getPendingReviews,
    getFindings,
    getChangelog,
    getLoanFileCost,
    deleteLoanFile,
} from "./api";
import FileDrawer from "./components/FileDrawer";
import RegisterLedger from "./components/RegisterLedger";
import ReviewQueue from "./components/ReviewQueue";
import FindingsList from "./components/FindingsList";
import ChangelogTicker from "./components/ChangelogTicker";
import DocumentToolbar from "./components/DocumentToolbar";
import CostReport from "./components/CostReport";

const TABS = ["Register", "Review Queue", "Findings", "Changelog", "Cost"];

function App() {
    const [loanFiles, setLoanFiles] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [activeTab, setActiveTab] = useState("Register");

    const [register, setRegister] = useState([]);
    const [reviewItems, setReviewItems] = useState([]);
    const [findings, setFindings] = useState([]);
    const [changelog, setChangelog] = useState([]);
    const [cost, setCost] = useState([]);
    const [refreshing, setRefreshing] = useState(false);

    useEffect(() => {
        refreshLoanFiles();
    }, []);

    useEffect(() => {
        refreshTabData();
    }, [selectedId]); // re-fetch everything when the selected loan file changes

    async function refreshTabData() {
        if (!selectedId) return;
        setRefreshing(true);
        await Promise.all([
            getRegister(selectedId).then(setRegister),
            getPendingReviews(selectedId).then(setReviewItems),
            getFindings(selectedId).then(setFindings),
            getChangelog(selectedId).then(setChangelog),
            getLoanFileCost(selectedId).then(setCost),
        ]);
        setRefreshing(false);
    }

    function refreshLoanFiles() {
        listLoanFiles().then(setLoanFiles);
    }

    async function handleDelete() {
        const confirmed = window.confirm(
            "Permanently delete this loan file and everything in it (documents, facts, register, history)? This cannot be undone.",
        );
        if (!confirmed) return;

        await deleteLoanFile(selectedId);
        setSelectedId(null);
        refreshLoanFiles();
    }

    return (
        <div className="min-h-screen p-8 flex gap-8">
            <FileDrawer
                loanFiles={loanFiles}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onCreated={refreshLoanFiles}
            />

            <div className="flex-1">
                {!selectedId ? (
                    <p className="font-body">
                        Select a loan file from the drawer.
                    </p>
                ) : (
                    <>
                        <DocumentToolbar
                            loanFileId={selectedId}
                            onDone={refreshTabData}
                        />
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex gap-1 border-b-2 border-ink flex-1">
                                {TABS.map((tab) => (
                                    <button
                                        key={tab}
                                        onClick={() => setActiveTab(tab)}
                                        className={`px-4 py-2 font-heading text-base border-2 border-b-0 border-ink -mb-0.5
                                            ${activeTab === tab ? "bg-card" : "bg-paper text-ink/50"}`}
                                    >
                                        {tab}
                                    </button>
                                ))}
                            </div>
                            <button
                                onClick={handleDelete}
                                className="border-2 border-stamp-red text-stamp-red px-3 py-1.5 font-mono text-sm hover:bg-stamp-red hover:text-card ml-3"
                            >
                                Delete File
                            </button>
                            <button
                                onClick={refreshTabData}
                                disabled={refreshing}
                                className="border-2 border-ink px-3 py-1.5 font-mono text-sm bg-card hover:bg-ink hover:text-card ml-3"
                                title="Refresh register, review queue, findings, and changelog"
                            >
                                {refreshing ? "Refreshing..." : "⟳ Refresh"}
                            </button>
                        </div>
                        {activeTab === "Register" && (
                            <RegisterLedger register={register} />
                        )}
                        {activeTab === "Review Queue" && (
                            <ReviewQueue
                                items={reviewItems}
                                onDecided={refreshTabData}
                            />
                        )}
                        {activeTab === "Findings" && (
                            <FindingsList findings={findings} />
                        )}
                        {activeTab === "Changelog" && (
                            <ChangelogTicker entries={changelog} />
                        )}
                        {activeTab === "Cost" && <CostReport cost={cost} />}
                    </>
                )}
            </div>
        </div>
    );
}

export default App;
