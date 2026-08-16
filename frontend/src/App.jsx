import { useState, useEffect } from "react";
import {
    listLoanFiles,
    getRegister,
    getPendingReviews,
    getFindings,
    getChangelog,
} from "./api";
import FileDrawer from "./components/FileDrawer";
import RegisterLedger from "./components/RegisterLedger";
import ReviewQueue from "./components/ReviewQueue";
import FindingsList from "./components/FindingsList";
import ChangelogTicker from "./components/ChangelogTicker";
import DocumentToolbar from "./components/DocumentToolbar";

const TABS = ["Register", "Review Queue", "Findings", "Changelog"];

function App() {
    const [loanFiles, setLoanFiles] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [activeTab, setActiveTab] = useState("Register");

    const [register, setRegister] = useState([]);
    const [reviewItems, setReviewItems] = useState([]);
    const [findings, setFindings] = useState([]);
    const [changelog, setChangelog] = useState([]);

    useEffect(() => {
        refreshLoanFiles();
    }, []);

    function refreshTabData() {
        if (!selectedId) return;
        getRegister(selectedId).then(setRegister);
        getPendingReviews(selectedId).then(setReviewItems);
        getFindings(selectedId).then(setFindings);
        getChangelog(selectedId).then(setChangelog);
    }

    function refreshLoanFiles() {
        listLoanFiles().then(setLoanFiles);
    }

    useEffect(refreshTabData, [selectedId]); // re-fetch everything when the selected loan file changes

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
                                onClick={refreshTabData}
                                className="border-2 border-ink px-3 py-1.5 font-mono text-sm bg-card hover:bg-ink hover:text-card ml-3"
                                title="Refresh register, review queue, findings, and changelog"
                            >
                                ⟳ Refresh
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
                    </>
                )}
            </div>
        </div>
    );
}

export default App;
