import { useState } from "react";
import Card from "./Card";
import StatusStamp from "./StatusStamp";
import { decideReviewItem } from "../api";

export default function ReviewQueue({ items, onDecided }) {
    const [busyId, setBusyId] = useState(null); // disables buttons on the item being decided, prevents double-clicks

    async function handleDecide(itemId, decision, keep = null) {
        setBusyId(itemId);
        await decideReviewItem(itemId, decision, keep);
        setBusyId(null);
        onDecided(); // parent re-fetches the queue, this item disappears once decided
    }

    if (items.length === 0)
        return <p className="font-body text-sm">Nothing pending.</p>;

    return (
        <div className="flex flex-col gap-3">
            {items.map((item) => (
                <Card key={item.item_id}>
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="font-mono text-sm font-bold">
                                {item.field_name}
                            </p>
                            <StatusStamp status={item.item_type} />
                            <div className="font-mono text-xs mt-2 space-y-1">
                                {item.old_value !== null && (
                                    <p className="text-stamp-red">
                                        old: {item.old_value}
                                    </p>
                                )}
                                <p className="text-stamp-green">
                                    new: {item.new_value}
                                </p>
                                {item.new_quote && (
                                    <p className="text-ink/50 italic">
                                        "{item.new_quote}"
                                    </p>
                                )}
                            </div>
                        </div>
                        <div className="flex gap-2">
                            {item.item_type === "conflict" && (
                                <>
                                    <button
                                        disabled={busyId === item.item_id}
                                        onClick={() =>
                                            handleDecide(
                                                item.item_id,
                                                "approve",
                                                "old",
                                            )
                                        }
                                        className="border-2 border-ink-blue text-ink-blue px-3 py-1 font-mono text-xs
                      hover:bg-ink-blue hover:text-card active:scale-95 transition"
                                    >
                                        Keep Old
                                    </button>
                                    <button
                                        disabled={busyId === item.item_id}
                                        onClick={() =>
                                            handleDecide(
                                                item.item_id,
                                                "approve",
                                                "new",
                                            )
                                        }
                                        className="border-2 border-stamp-green text-stamp-green px-3 py-1 font-mono text-xs
                      hover:bg-stamp-green hover:text-card active:scale-95 transition"
                                    >
                                        Keep New
                                    </button>
                                </>
                            )}
                            {item.item_type === "register_update" && (
                                <button
                                    disabled={busyId === item.item_id}
                                    onClick={() =>
                                        handleDecide(item.item_id, "approve")
                                    }
                                    className="border-2 border-stamp-green text-stamp-green px-3 py-1 font-mono text-xs
                    hover:bg-stamp-green hover:text-card active:scale-95 transition"
                                >
                                    Approve
                                </button>
                            )}
                            <button
                                disabled={busyId === item.item_id}
                                onClick={() =>
                                    handleDecide(item.item_id, "reject")
                                }
                                className="border-2 border-stamp-red text-stamp-red px-3 py-1 font-mono text-xs
                  hover:bg-stamp-red hover:text-card active:scale-95 transition"
                            >
                                Reject
                            </button>
                        </div>
                    </div>
                </Card>
            ))}
        </div>
    );
}
