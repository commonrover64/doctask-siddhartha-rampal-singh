import { useState, useEffect } from "react";
import { getRegister } from "../api";

export default function RegisterPage({ loanFileId }) {
  const [register, setRegister] = useState([]);

  useEffect(() => {
    getRegister(loanFileId).then(setRegister);
  }, [loanFileId]);  // re-fetches whenever the selected loan file changes

  return (
    <>
      <h2 className="text-lg font-medium mb-4">Register</h2>
      <div className="border border-surface1 rounded-md overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface0 text-subtext0 text-left">
              <th className="px-4 py-2 font-medium">Field</th>
              <th className="px-4 py-2 font-medium">Value</th>
              <th className="px-4 py-2 font-medium">Source quote</th>
            </tr>
          </thead>
          <tbody>
            {register.map((r) => (
              <tr key={r.field_name} className="border-t border-surface1">
                <td className="px-4 py-2 text-subtext0">{r.field_name}</td>
                <td className="px-4 py-2 font-mono">{r.field_value}</td>
                <td className="px-4 py-2 text-subtext0 italic">{r.quote}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {register.length === 0 && (
          <p className="px-4 py-6 text-center text-overlay0">
            No approved fields yet for this loan file.
          </p>
        )}
      </div>
    </>
  );
}