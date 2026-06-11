const STRUCTURE_TYPES = [
  { value: "standing_stone", label: "Standing Stone (⬣)" },
  { value: "abandoned_shack", label: "Abandoned Shack (⌂)" },
];

const STRUCTURE_COLORS = ["white", "green", "blue", "black"];

export function StructurePanel({
  structureType,
  structureColor,
  isBusy,
  hasSelection,
  onStructureTypeChange,
  onStructureColorChange,
  onSave,
  onRemove,
}) {
  const canSave = Boolean(structureType) && Boolean(structureColor) && !isBusy;

  return (
    <div className="entry-panel">
      <label>
        Tipo edificio
        <select
          value={structureType}
          onChange={(event) => onStructureTypeChange(event.target.value)}
          disabled={isBusy}
        >
          <option value="">Seleziona tipo</option>
          {STRUCTURE_TYPES.map((entry) => (
            <option key={entry.value} value={entry.value}>{entry.label}</option>
          ))}
        </select>
      </label>

      <label>
        Colore edificio
        <select
          value={structureColor}
          onChange={(event) => onStructureColorChange(event.target.value)}
          disabled={isBusy}
        >
          <option value="">Seleziona colore</option>
          {STRUCTURE_COLORS.map((color) => (
            <option key={color} value={color}>{color}</option>
          ))}
        </select>
      </label>

      <button onClick={onSave} disabled={!canSave || !hasSelection}>Salva edificio</button>
      <button onClick={onRemove} disabled={isBusy || !hasSelection}>Rimuovi edificio</button>
    </div>
  );
}

