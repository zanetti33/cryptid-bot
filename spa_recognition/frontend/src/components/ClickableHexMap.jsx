const TERRAIN_COLORS = {
  forest: "#4f8a3f",
  mountain: "#7b7b7b",
  water: "#3d74c5",
  desert: "#d7b65a",
  swamp: "#7b5aa6",
  unknown: "#4f4f4f",
};

const STRUCTURE_ICONS = {
  standing_stone: "⬣",
  abandoned_shack: "⌂",
};

const STRUCTURE_COLOR_CLASSES = {
  white: "structure-white",
  green: "structure-green",
  blue: "structure-blue",
  black: "structure-black",
};

const ANIMAL_BORDER_CLASSES = {
  bear: "animal-bear",
  cougar: "animal-cougar",
};

function getAnimalClass(animal) {
  return ANIMAL_BORDER_CLASSES[animal] || "";
}

function getContrastColor(terrain) {
  return terrain === "desert" ? "#1f1f1f" : "#ffffff";
}

function buildFallbackTiles(cols, rows) {
  return Array.from({ length: cols * rows }, (_, index) => ({
    tile_id: index,
    q: index % cols,
    r: Math.floor(index / cols),
    terrain: "unknown",
    section_id: null,
    local_id: null,
  }));
}

function computeGridSize(tiles, fallbackCols, fallbackRows) {
  if (!tiles.length) {
    return { cols: fallbackCols, rows: fallbackRows };
  }

  const maxQ = Math.max(...tiles.map((tile) => tile.q ?? 0));
  const maxR = Math.max(...tiles.map((tile) => tile.r ?? 0));
  return { cols: maxQ + 1, rows: maxR + 1 };
}

function playerTokenLabel(playerId, playerLabelsById) {
  return playerLabelsById?.[playerId] || playerId;
}

export function ClickableHexMap({
  cols = 12,
  rows = 9,
  tiles = [],
  playerLabelsById = {},
  selectedTileId,
  onTileClick,
  disabled = false,
  showAnimals = true,
  showStructures = true,
  showTokens = true,
}) {
  const resolvedTiles = tiles.length ? tiles : buildFallbackTiles(cols, rows);
  const gridSize = computeGridSize(resolvedTiles, cols, rows);

  return (
    <div
      className="hex-grid"
      style={{
        gridTemplateColumns: `repeat(${gridSize.cols}, minmax(40px, 1fr))`,
      }}
    >
      {resolvedTiles.map((tile) => {
        const isSelected = tile.tile_id === selectedTileId;
        const terrain = tile.terrain || "unknown";
        const animal = tile.animal || null;
        const animalClass = showAnimals && animal ? getAnimalClass(animal) : "";
        const structureType = tile.structure_type || null;
        const structureColor = tile.structure_color || null;
        const roundTokenCount = tile.round_token_count || 0;
        const cubeTokenCount = tile.cube_token_count || 0;
        const roundTokens = tile.round_tokens || [];
        const cubeTokens = tile.cube_tokens || [];
        const roundTokenLabels = roundTokens.map((playerId) => `${playerTokenLabel(playerId, playerLabelsById)}:${playerId}`);
        const cubeTokenLabels = cubeTokens.map((playerId) => `${playerTokenLabel(playerId, playerLabelsById)}:${playerId}`);
        const tokenTitle = showTokens
          ? ` | round: ${roundTokenCount} (${roundTokenLabels.join(", ") || "-"}) | cube: ${cubeTokenCount} (${cubeTokenLabels.join(", ") || "-"})`
          : "";
        return (
          <button
            key={tile.tile_id}
            className={`hex-cell ${animalClass} ${isSelected ? "selected" : ""}`}
            onClick={() => onTileClick(tile.tile_id)}
            title={`Tile ${tile.tile_id} · ${terrain}${tokenTitle}`}
            disabled={disabled}
            style={{
              gridColumn: (tile.q ?? 0) + 1,
              gridRow: (tile.r ?? 0) + 1,
              backgroundColor: TERRAIN_COLORS[terrain] || TERRAIN_COLORS.unknown,
              color: getContrastColor(terrain),
              // Offset even columns (2nd, 4th, …) down by half a cell height
              transform: (tile.q ?? 0) % 2 === 1 ? "translateY(50%)" : undefined,
            }}
          >
            <span className="overlay-icons overlay-icons-tight">
              {showTokens ? (
                <span className="token-stack">
                  {roundTokens.map((playerId) => (
                    <span key={`round-${tile.tile_id}-${playerId}`} className="token-badge token-round">
                      ●{playerTokenLabel(playerId, playerLabelsById)}
                    </span>
                  ))}
                  {cubeTokens.map((playerId) => (
                    <span key={`cube-${tile.tile_id}-${playerId}`} className="token-badge token-cube">
                      ■{playerTokenLabel(playerId, playerLabelsById)}
                    </span>
                  ))}
                </span>
              ) : null}
              {showStructures && structureType ? (
                <span
                  className={`structure-icon ${STRUCTURE_COLOR_CLASSES[structureColor] || ""}`}
                  title={`${structureType} (${structureColor || "unknown"})`}
                >
                  {STRUCTURE_ICONS[structureType] || "◆"}
                </span>
              ) : null}
            </span>
          </button>
        );
      })}
    </div>
  );
}

