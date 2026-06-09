import { useMemo, useState } from "react";

import { postEndpoint } from "./api/client";
import { ClickableHexMap } from "./components/ClickableHexMap";
import { ModeSwitcher } from "./components/ModeSwitcher";
import { Toolbar } from "./components/Toolbar";

const DEFAULT_SESSION_ID = "default";

export function App() {
  const [mode, setMode] = useState("structures");
  const [phase, setPhase] = useState("setup");
  const [selectedTileId, setSelectedTileId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [response, setResponse] = useState(null);

  const warnings = useMemo(() => response?.warnings || [], [response]);
  const moves = useMemo(() => response?.data?.recommended_moves || [], [response]);

  async function bootstrapSession() {
    setBusy(true);
    try {
      const setup = await postEndpoint("/setup", {
        session_id: DEFAULT_SESSION_ID,
        player_ids: ["bot", "p1", "p2"],
        turn_order: ["bot", "p1", "p2"],
        bot_player_id: "bot",
      });

      await postEndpoint("/map", {
        session_id: DEFAULT_SESSION_ID,
        cols: 12,
        rows: 9,
        observed_tokens: [],
      });

      setResponse(setup);
      setPhase(setup.session.phase);
    } finally {
      setBusy(false);
    }
  }

  async function saveModeEntry() {
    if (selectedTileId === null) {
      return;
    }

    setBusy(true);
    try {
      if (mode === "structures") {
        const result = await postEndpoint("/structures", {
          session_id: DEFAULT_SESSION_ID,
          structures: [
            {
              tile_id: selectedTileId,
              structure_type: "standing_stone",
              structure_color: "white",
            },
          ],
        });
        setResponse(result);
        setPhase(result.session.phase);
      } else {
        const result = await postEndpoint("/clues", {
          session_id: DEFAULT_SESSION_ID,
          by_player_id: {
            bot: {
              notes: [`Selected tile ${selectedTileId}`],
            },
          },
        });
        setResponse(result);
        setPhase(result.session.phase);
      }
    } finally {
      setBusy(false);
    }
  }

  async function recalculate() {
    setBusy(true);
    try {
      const result = await postEndpoint("/recalculate", {
        session_id: DEFAULT_SESSION_ID,
        top_k: 5,
      });
      setResponse(result);
      setPhase(result.session.phase);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <h1>Cryptid SPA Recognition (MVP)</h1>

      <Toolbar phase={phase} onRecalculate={recalculate} isBusy={busy} />
      <ModeSwitcher mode={mode} onChange={setMode} />

      <div className="actions">
        <button onClick={bootstrapSession} disabled={busy}>Bootstrap Session</button>
        <button onClick={saveModeEntry} disabled={busy || selectedTileId === null}>
          Save {mode === "structures" ? "Structure" : "Clue"}
        </button>
      </div>

      <ClickableHexMap selectedTileId={selectedTileId} onTileClick={setSelectedTileId} />

      <section>
        <h2>Warnings</h2>
        <pre>{JSON.stringify(warnings, null, 2)}</pre>
      </section>

      <section>
        <h2>Recommended Moves</h2>
        <pre>{JSON.stringify(moves, null, 2)}</pre>
      </section>
    </main>
  );
}

