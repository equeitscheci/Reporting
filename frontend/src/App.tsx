import { useState } from "react";
import { Dashboard } from "./components/Dashboard";
import { Insights } from "./components/Insights";
import { ReportBuilder } from "./builder/ReportBuilder";
import { api } from "./api";

type View = "dashboards" | "builder" | "insights";

export default function App() {
  const [view, setView] = useState<View>("dashboards");
  const [syncing, setSyncing] = useState(false);
  const [synced, setSynced] = useState(false);

  const sync = async () => {
    setSyncing(true);
    try {
      await api.runSync();
      setSynced(true);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◆</span> Insightforge
          <span className="tenant">tenant: {api.tenant}</span>
        </div>
        <nav>
          {(["dashboards", "builder", "insights"] as View[]).map((v) => (
            <button key={v} className={`nav ${view === v ? "active" : ""}`} onClick={() => setView(v)}>
              {v === "builder" ? "Report Builder" : v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          ))}
          <button className="sync" onClick={sync} disabled={syncing}>
            {syncing ? "Syncing…" : synced ? "Re-sync ERP" : "Sync ERP"}
          </button>
        </nav>
      </header>

      <main>
        {view === "dashboards" && <Dashboard />}
        {view === "builder" && <ReportBuilder />}
        {view === "insights" && <Insights />}
      </main>
    </div>
  );
}
