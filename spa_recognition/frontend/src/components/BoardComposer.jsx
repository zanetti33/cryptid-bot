const FALLBACK_SLOTS = [
  { slot_id: 1, origin_q: 0, origin_r: 0 },
  { slot_id: 2, origin_q: 6, origin_r: 0 },
  { slot_id: 3, origin_q: 0, origin_r: 3 },
  { slot_id: 4, origin_q: 6, origin_r: 3 },
  { slot_id: 5, origin_q: 0, origin_r: 6 },
  { slot_id: 6, origin_q: 6, origin_r: 6 },
];

const FALLBACK_SECTIONS = ["A", "B", "C", "D", "E", "F"];
const FALLBACK_ORIENTATIONS = ["normal", "flipped"];

function getPlacementBySlot(placements, slotId) {
  return placements.find((entry) => entry.slot_id === slotId) || null;
}

function moduleLabel(sectionId) {
  if (typeof sectionId !== "string" || sectionId.length !== 1) {
    return sectionId;
  }
  const index = sectionId.charCodeAt(0) - 64;
  return index >= 1 && index <= 26 ? String(index) : sectionId;
}

export function BoardComposer({
  catalog,
  placements,
  onPlacementChange,
  onApply,
  isBusy,
  isComplete,
}) {
  const slots = catalog?.slots || FALLBACK_SLOTS;
  const sections = catalog?.sections || FALLBACK_SECTIONS;
  const orientations = catalog?.orientations || FALLBACK_ORIENTATIONS;

  return (
    <section className="panel-section">
      <div className="panel-header">
        <div>
          <h2>1. Componi la board</h2>
          <p>Assegna un modulo a ciascuno dei 6 slot prima di applicare il layout.</p>
        </div>
        <button onClick={onApply} disabled={isBusy}>
          {isBusy ? "Applicazione..." : "Applica layout board"}
        </button>
      </div>

      <div className="status-row">
        <span className={`status-pill ${isComplete ? "success" : "pending"}`}>
          {isComplete ? "Board layout complete" : "Board layout incomplete"}
        </span>
      </div>

      <div className="board-composer-grid">
        {slots.map((slot) => {
          const placement = getPlacementBySlot(placements, slot.slot_id);
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
                >
                  <option value="">Seleziona modulo</option>
                  {sections.map((sectionId) => (
                    <option key={sectionId} value={sectionId}>
                      {moduleLabel(sectionId)}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Orientation
                <select
                  value={placement?.orientation || "normal"}
                  onChange={(event) => onPlacementChange(slot.slot_id, "orientation", event.target.value)}
                >
                  {orientations.map((orientation) => (
                    <option key={orientation} value={orientation}>
                      {orientation}
                    </option>
                  ))}
                </select>
              </label>
            </article>
          );
        })}
      </div>
    </section>
  );
}

