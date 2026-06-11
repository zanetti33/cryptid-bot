const TOKEN_TYPES = [
  { value: "round", label: "Round (●)" },
  { value: "cube", label: "Cube (■)" },
];

export function TokenPanel({
  playerIds,
  tokenPlayerId,
  tokenType,
  isBusy,
  hasSelection,
  onTokenPlayerChange,
  onTokenTypeChange,
  onSave,
  onRemove,
}) {
  const canSave = Boolean(tokenPlayerId) && Boolean(tokenType) && !isBusy;

  return (
    <div className="entry-panel">
      <label>
        Giocatore clue
        <select
          value={tokenPlayerId || ""}
          onChange={(event) => onTokenPlayerChange(event.target.value)}
          disabled={isBusy}
        >
          <option value="">Seleziona giocatore</option>
          {playerIds.map((playerId) => (
            <option key={playerId} value={playerId}>{playerId}</option>
          ))}
        </select>
      </label>

      <label>
        Tipo clue
        <select
          value={tokenType}
          onChange={(event) => onTokenTypeChange(event.target.value)}
          disabled={isBusy}
        >
          <option value="">Seleziona tipo</option>
          {TOKEN_TYPES.map((entry) => (
            <option key={entry.value} value={entry.value}>{entry.label}</option>
          ))}
        </select>
      </label>

      <button onClick={onSave} disabled={!canSave || !hasSelection}>Salva clue</button>
      <button onClick={onRemove} disabled={!canSave || !hasSelection}>Rimuovi clue</button>
    </div>
  );
}

