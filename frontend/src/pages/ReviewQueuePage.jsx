import { useState, useEffect, useCallback } from "react";
import { listPending, decideReviewItem } from "../api";

const STATUS_STYLES = {
    conflict: "border-status-violation",
    register_update: "border-status-pending",
};

export default function ReviewQueuePage({ loanFileId }) {
    const [items, setItems] = useState([]);
    const [busyId, setBusyId] = useState(null); // disables buttons on the item being decided, prevents double-clicks

    const refresh = useCallback(() => {
        listPending(loanFileId).then(setItems);
    }, [loanFileId]);

    useEffect(() => {
        refresh();
    }, [refresh]);

    async function handleDecide(itemId, decision, keep) {
        setBusyId(itemId);
        try {
            await decideReviewItem(itemId, decision, keep);
            await refresh(); // re-fetch rather than local-splice, keeps this in sync with anything else touching the queue
        } finally {
            setBusyId(null);
        }
    }

    return (
        <>
            <h2 className="text-lg font-medium mb-4">Review Queue</h2>
            {items.length === 0 ? (
                <p className="text-overlay0">No items pending review.</p>
            ) : (
                <ul className="space-y-3">
                    {items.map((item) => (
                        <li
                            key={item.item_id}
                            className={`border-l-2 bg-surface0 rounded-md px-4 py-3 ${STATUS_STYLES[item.item_type]}`}
                        >
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex-1">
                                    <p className="font-medium">
                                        {item.field_name}
                                    </p>
                                    <p className="text-sm text-subtext0 capitalize mb-2">
                                        {item.item_type.replace("_", " ")}
                                    </p>

                                    {item.item_type === "conflict" ? (
                                        <div className="grid grid-cols-2 gap-3 text-sm">
                                            <div>
                                                <p className="text-subtext0 text-xs uppercase mb-1">
                                                    Old value
                                                </p>
                                                <p className="font-mono">
                                                    {item.old_value}
                                                </p>
                                                <p className="text-overlay0 italic text-xs mt-1">
                                                    "{item.old_quote}"
                                                </p>
                                            </div>
                                            <div>
                                                <p className="text-subtext0 text-xs uppercase mb-1">
                                                    New value
                                                </p>
                                                <p className="font-mono">
                                                    {item.new_value}
                                                </p>
                                                <p className="text-overlay0 italic text-xs mt-1">
                                                    "{item.new_quote}"
                                                </p>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="text-sm">
                                            <p className="font-mono">
                                                {item.new_value}
                                            </p>
                                            <p className="text-overlay0 italic text-xs mt-1">
                                                "{item.quote}"
                                            </p>
                                        </div>
                                    )}
                                </div>

                                <div className="flex gap-2 shrink-0">
                                    {item.item_type === "conflict" ? (
                                        <>
                                            <button
                                                disabled={
                                                    busyId === item.item_id
                                                }
                                                onClick={() =>
                                                    handleDecide(
                                                        item.item_id,
                                                        "approve",
                                                        "old",
                                                    )
                                                }
                                                className="px-3 py-1.5 text-sm rounded border border-surface1 hover:bg-surface1 disabled:opacity-50"
                                            >
                                                Keep old
                                            </button>
                                            <button
                                                disabled={
                                                    busyId === item.item_id
                                                }
                                                onClick={() =>
                                                    handleDecide(
                                                        item.item_id,
                                                        "approve",
                                                        "new",
                                                    )
                                                }
                                                className="px-3 py-1.5 text-sm rounded border border-surface1 hover:bg-surface1 disabled:opacity-50"
                                            >
                                                Keep new
                                            </button>
                                        </>
                                    ) : (
                                        <button
                                            disabled={busyId === item.item_id}
                                            onClick={() =>
                                                handleDecide(
                                                    item.item_id,
                                                    "approve",
                                                )
                                            }
                                            className="px-3 py-1.5 text-sm rounded bg-status-clean/20 text-status-clean hover:bg-status-clean/30 disabled:opacity-50"
                                        >
                                            Approve
                                        </button>
                                    )}
                                    <button
                                        disabled={busyId === item.item_id}
                                        onClick={() =>
                                            handleDecide(item.item_id, "reject")
                                        }
                                        className="px-3 py-1.5 text-sm rounded bg-status-violation/20 text-status-violation hover:bg-status-violation/30 disabled:opacity-50"
                                    >
                                        Reject
                                    </button>
                                </div>
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </>
    );
}
