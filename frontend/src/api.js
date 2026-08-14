const BASE_URL = import.meta.env.VITE_API_BASE_URL;

async function request(path, options = {}) {
    const res = await fetch(`${BASE_URL}${path}`, {
        headers: {
            "Content-Type": "application/json",
        },
        ...options,
    });

    if (!res.ok) {
        const body = await res.text();
        throw new Error(`${res.status} ${path}: ${body}`); // one place errors surface, instead of every caller checking res.ok itself
    }

    return res.json();
}

export const listLoanFiles = () => request("/loan-files");
export const getRegister = (loanFileId) =>
    request(`/loan-files/${loanFileId}/register`);
