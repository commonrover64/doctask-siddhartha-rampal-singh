import Card from "./Card";
import StatusStamp from "./StatusStamp";

export default function FindingsList({ findings }) {
    if (findings.length === 0)
        return <p className="font-body text-sm">No check run yet.</p>;

    return (
        <div className="flex flex-col gap-3">
            {findings.map((f) => (
                <Card key={f.finding_id}>
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="font-mono text-xs text-ink/60">
                                {f.stage}
                            </p>
                            <p className="font-mono text-sm font-bold">
                                {f.rule_id}
                            </p>
                            <p className="font-body text-sm mt-1">
                                {f.detail
                                    .split(";")
                                    .map((line, index, lines) => (
                                        <span key={index}>
                                            {line.trim()}
                                            {index < lines.length - 1 && ";"}
                                            <br />
                                        </span>
                                    ))}
                            </p>
                        </div>
                        <StatusStamp status={f.status} />
                    </div>
                </Card>
            ))}
        </div>
    );
}
