export function Toolbar({
  phase,
  hasBoardLayout,
  showAnimals,
  showStructures,
  showTokens,
  onToggleAnimals,
  onToggleStructures,
  onToggleTokens,
}) {
  return (
    <div className="toolbar">
      <span>Phase: {phase}</span>
      <span>Board: {hasBoardLayout ? "ready" : "not configured"}</span>
      <label className="toggle-item">
        <input type="checkbox" checked={showAnimals} onChange={onToggleAnimals} /> Animals
      </label>
      <label className="toggle-item">
        <input type="checkbox" checked={showStructures} onChange={onToggleStructures} /> Structures
      </label>
      <label className="toggle-item">
        <input type="checkbox" checked={showTokens} onChange={onToggleTokens} /> Tokens
      </label>
    </div>
  );
}

