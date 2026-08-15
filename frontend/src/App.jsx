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
        listLoanFiles().then(setLoanFiles);
    }, []);

    function refreshTabData() {
        if (!selectedId) return;
        getRegister(selectedId).then(setRegister);
        getPendingReviews(selectedId).then(setReviewItems);
        getFindings(selectedId).then(setFindings);
        getChangelog(selectedId).then(setChangelog);
    }

    useEffect(refreshTabData, [selectedId]); // re-fetch everything when the selected loan file changes

    return (
        <div className="min-h-screen p-8 flex gap-8">
            <FileDrawer
                loanFiles={loanFiles}
                selectedId={selectedId}
                onSelect={setSelectedId}
            />

            <div className="flex-1">
                {!selectedId ? (
                    <p className="font-body">
                        Select a loan file from the drawer.
                    </p>
                ) : (
                    <>
                        <div className="flex gap-1 mb-4 border-b-2 border-ink">
                            {TABS.map((tab) => (
                                <button
                                    key={tab}
                                    onClick={() => setActiveTab(tab)}
                                    className={`px-4 py-2 font-heading text-sm border-2 border-b-0 border-ink -mb-0.5
                    ${activeTab === tab ? "bg-card" : "bg-paper text-ink/50"}`}
                                >
                                    {tab}
                                </button>
                            ))}
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
