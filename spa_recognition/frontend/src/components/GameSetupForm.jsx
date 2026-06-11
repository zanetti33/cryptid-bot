function clueGroupLabel(clueId) {
  if (typeof clueId !== "string") {
    return "Altre clue";
  }
  if (clueId.startsWith("terrain_pair_")) {
    return "Terreno (coppie)";
  }
  if (clueId.startsWith("within_one_") && !clueId.includes("animal")) {
    return "Terreno (entro 1)";
  }
  if (clueId.startsWith("within_one_") && clueId.includes("animal")) {
    return "Animali (entro 1)";
  }
  if (clueId.startsWith("within_two_") && clueId.includes("territory")) {
    return "Animali (entro 2)";
  }
  if (clueId.startsWith("within_two_") && (clueId.includes("standing_stone") || clueId.includes("abandoned_shack"))) {
    return "Strutture per tipo (entro 2)";
  }
  if (clueId.startsWith("within_three_") && clueId.includes("structure")) {
    return "Strutture per colore (entro 3)";
  }
  return "Altre clue";
}

function groupCluesByType(clueCatalog) {
  const grouped = new Map();
  for (const clue of clueCatalog) {
    const label = clueGroupLabel(clue?.clue_id);
    if (!grouped.has(label)) {
      grouped.set(label, []);
    }
    grouped.get(label).push(clue);
  }
  return Array.from(grouped.entries());
}

function moduleLabel(sectionId) {
  if (typeof sectionId !== "string" || sectionId.length !== 1) {
    return sectionId;
  }
  const index = sectionId.charCodeAt(0) - 64;
  return index >= 1 && index <= 26 ? String(index) : sectionId;
}

export function GameSetupForm({
  playerCount,
  playerIds,
  turnOrder,
  botPlayerId,
  botClueId,
  clueCatalog,
  isSetupValid,
  isBusy,
  onPlayerCountChange,
  onTurnOrderChange,
  onBotPlayerChange,
  onBotClueChange,
  onSubmit,
  boardCatalog,
  placements,
  onPlacementChange,
  onApplyBoardLayout,
  isBoardLayoutComplete,
}) {
  const groupedClues = groupCluesByType(clueCatalog);
  const slots = boardCatalog?.slots || [];
  const sections = boardCatalog?.sections || [];
  const orientations = boardCatalog?.orientations || ["normal", "flipped"];

  function placementForSlot(slotId) {
    return placements.find((entry) => entry.slot_id === slotId) || null;
  }

  return (
    <section className="panel-section">
      <div className="panel-header">
        <div>
          <h2>1. Setup partita</h2>
          <p>
            I giocatori vengono assegnati automaticamente ({playerIds.join(", ")}).
            Configura ordine di turno, giocatore AI e clue del bot.
          </p>
        </div>
      </div>

      <div className="setup-grid">
        <label>
          Numero giocatori
          <select
            value={playerCount}
            onChange={(event) => onPlayerCountChange(Number(event.target.value))}
            disabled={isBusy}
          >
            {[2, 3, 4, 5].map((count) => (
              <option key={count} value={count}>{count}</option>
            ))}
          </select>
        </label>

        {Array.from({ length: playerCount }, (_, index) => (
          <label key={index}>
            Turno {index + 1}
            <select
              value={turnOrder[index] || ""}
              onChange={(event) => onTurnOrderChange(index, event.target.value)}
              disabled={isBusy}
            >
              {playerIds.map((playerId) => (
                <option key={playerId} value={playerId}>{playerId}</option>
              ))}
            </select>
          </label>
        ))}

        <label>
          Giocatore AI
          <select
            value={botPlayerId || ""}
            onChange={(event) => onBotPlayerChange(event.target.value)}
            disabled={isBusy || playerIds.length === 0}
          >
            <option value="">Seleziona AI</option>
            {playerIds.map((playerId) => (
              <option key={playerId} value={playerId}>{playerId}</option>
            ))}
          </select>
        </label>

        <label>
          Clue AI
          <select
            value={botClueId || ""}
            onChange={(event) => onBotClueChange(event.target.value)}
            disabled={isBusy}
          >
            <option value="">{clueCatalog.length ? "Seleziona clue" : "Catalogo clue non caricato"}</option>
            {groupedClues.map(([groupLabel, clues]) => (
              <optgroup key={groupLabel} label={groupLabel}>
                {clues.map((clue) => (
                  <option key={clue.clue_id} value={clue.clue_id}>
                    {clue.text}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

      </div>

      <div className="panel-header">
        <div>
          <h3>Module template</h3>
          <p>Assegna un modulo a ciascun board slot prima di applicare il layout.</p>
        </div>
      </div>

      <div className="status-row">
        <span className={`status-pill ${isBoardLayoutComplete ? "success" : "pending"}`}>
          {isBoardLayoutComplete ? "Board layout complete" : "Board layout incomplete"}
        </span>
      </div>

      {slots.length > 0 ? (
        <div className="board-composer-grid">
          {slots.map((slot) => {
            const placement = placementForSlot(slot.slot_id);
            return (
              <article key={slot.slot_id} className="board-slot-card">
                <h3>Slot {slot.slot_id}</h3>
                <p className="slot-meta">
                  origin q={slot.origin_q}, r={slot.origin_r}
                </p>

                <label>
                  Modulo
                  <select
                    value={placement?.section_id || ""}
                    onChange={(event) => onPlacementChange(slot.slot_id, "section_id", event.target.value)}
                    disabled={isBusy}
                  >
                    <option value="">Seleziona modulo</option>
                    {sections.map((sectionId) => (
                      <option key={sectionId} value={sectionId}>{moduleLabel(sectionId)}</option>
                    ))}
                  </select>
                </label>

                <label>
                  Orientation
                  <select
                    value={placement?.orientation || "normal"}
                    onChange={(event) => onPlacementChange(slot.slot_id, "orientation", event.target.value)}
                    disabled={isBusy}
                  >
                    {orientations.map((orientation) => (
                      <option key={orientation} value={orientation}>{orientation}</option>
                    ))}
                  </select>
                </label>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="slot-meta">Catalogo board non disponibile: avvia la sessione.</p>
      )}

      <div className="layout-actions-row">
        <p className="slot-meta">Modalita' manuale: configura i moduli e poi applica il layout.</p>
        <button type="button" onClick={onApplyBoardLayout} disabled={isBusy || slots.length === 0}>
          {isBusy ? "Applicazione..." : "Applica layout board"}
        </button>
      </div>

      <div className="actions">
        <button onClick={onSubmit} disabled={isBusy || !isSetupValid}>
          {isBusy ? "Configurazione..." : "Avvia sessione"}
        </button>
      </div>
    </section>
  );
}


