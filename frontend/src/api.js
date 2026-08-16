const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function listLoanFiles() {
    const res = await fetch(`${BASE_URL}/loan-files`);
    return res.json();
}

export async function getRegister(loanFileId) {
    const res = await fetch(`${BASE_URL}/loan-files/${loanFileId}/register`);
    return res.json();
}

export async function getPendingReviews(loanFileId) {
    const res = await fetch(`${BASE_URL}/review/${loanFileId}/pending`);
    return res.json();
}

export async function decideReviewItem(itemId, decision, keep = null) {
    const res = await fetch(`${BASE_URL}/review/${itemId}/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, keep }),
    });
    return res.json();
}

export async function getFindings(loanFileId) {
    const res = await fetch(`${BASE_URL}/loan-files/${loanFileId}/findings`);
    return res.json();
}

export async function getChangelog(loanFileId) {
    const res = await fetch(`${BASE_URL}/loan-files/${loanFileId}/changelog`);
    return res.json();
}

export async function createLoanFile(borrowerName) {
    const res = await fetch(`${BASE_URL}/loan-files`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ borrower_name: borrowerName }),
    });
    return res.json();
}

export async function uploadDocument(loanFileId, file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/loan-files/${loanFileId}/documents`, {
        method: "POST",
        body: formData, // no Content-Type header, the browser sets the multipart boundary itself
    });
    return res.json();
}

export async function processDocument(documentId) {
    const res = await fetch(`${BASE_URL}/documents/${documentId}/process`, {
        method: "POST",
    });
    return res.json();
}

export async function checkLoanFile(loanFileId) {
    const res = await fetch(`${BASE_URL}/loan-files/${loanFileId}/check`, {
        method: "POST",
    });
    return res.json();
}

export async function getLoanFileCost(loanFileId) {
    const res = await fetch(`${BASE_URL}/loan-files/${loanFileId}/cost`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
}

export async function listDocuments(loanFileId) {
  const res = await fetch(`${BASE_URL}/loan-files/${loanFileId}/documents`);
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}