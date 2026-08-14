import { useState, useEffect } from "react";
import { listLoanFiles } from "./api";
import Sidebar from "./components/Sidebar";
import RegisterPage from "./pages/RegisterPage";

function App() {
  const [loanFiles, setLoanFiles] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    listLoanFiles().then(setLoanFiles);
  }, []);

  return (
    <div className="flex h-screen bg-base font-sans text-text">
      <Sidebar loanFiles={loanFiles} selectedId={selectedId} onSelect={setSelectedId} />
      <main className="flex-1 overflow-y-auto p-8">
        {selectedId ? (
          <RegisterPage loanFileId={selectedId} />
        ) : (
          <p className="text-overlay0">Select a loan file to view its register.</p>
        )}
      </main>
    </div>
  );
}

export default App;