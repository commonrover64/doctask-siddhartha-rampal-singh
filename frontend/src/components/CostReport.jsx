import Card from "./Card";

export default function CostReport({ cost }) {
    const rows = Array.isArray(cost) ? cost : []; // never assume the prop is shaped correctly

    if (rows.length === 0)
        return <p className="font-body text-sm">No LLM calls recorded yet.</p>;

    const totalIn = rows.reduce((sum, c) => sum + Number(c.tokens_in), 0);
    const totalOut = rows.reduce((sum, c) => sum + Number(c.tokens_out), 0);

    return (
        <Card>
            <table className="w-full font-mono text-sm">
                <thead>
                    <tr className="border-b-2 border-ink text-left">
                        <th className="pb-2">Stage</th>
                        <th className="pb-2">Calls</th>
                        <th className="pb-2">Tokens In</th>
                        <th className="pb-2">Tokens Out</th>
                        <th className="pb-2">Latency</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((c) => (
                        <tr key={c.stage} className="border-b border-ink/20">
                            <td className="py-2 pr-4">{c.stage}</td>
                            <td className="py-2 pr-4">{c.call_count}</td>
                            <td className="py-2 pr-4">{c.tokens_in}</td>
                            <td className="py-2 pr-4">{c.tokens_out}</td>
                            <td className="py-2">{c.latency_ms}ms</td>
                        </tr>
                    ))}
                </tbody>
            </table>
            <p className="font-mono text-sm text-ink/60 mt-3">
                Total: {totalIn} in / {totalOut} out. Groq's free tier isn't
                billed per-token, so no dollar cost applies here.
            </p>
        </Card>
    );
}
