import Card from "./Card";

export default function RegisterLedger({ register }) {
    if (register.length === 0)
        return <p className="font-body text-sm">No approved fields yet.</p>;

    return (
        <Card>
            <table className="w-full font-mono text-sm">
                <thead>
                    <tr className="border-b-2 border-ink text-left">
                        <th className="pb-2">Field</th>
                        <th className="pb-2">Value</th>
                        <th className="pb-2">Quote</th>
                    </tr>
                </thead>
                <tbody>
                    {register.map((r) => (
                        <tr
                            key={r.field_name}
                            className="border-b border-ink/20"
                        >
                            <td className="py-2 pr-4">{r.field_name}</td>
                            <td className="py-2 pr-4">{r.field_value}</td>
                            <td className="py-2 text-ink/60 italic">
                                {r.quote}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </Card>
    );
}
