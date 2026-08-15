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
