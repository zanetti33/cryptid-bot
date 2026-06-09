function buildTileIds(cols, rows) {
  return Array.from({ length: cols * rows }, (_, index) => index);
}

export function ClickableHexMap({ cols = 12, rows = 9, selectedTileId, onTileClick }) {
  const tileIds = buildTileIds(cols, rows);

  return (
    <div className="hex-grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(40px, 1fr))` }}>
      {tileIds.map((tileId) => {
        const isSelected = tileId === selectedTileId;
        return (
          <button
            key={tileId}
            className={`hex-cell ${isSelected ? "selected" : ""}`}
            onClick={() => onTileClick(tileId)}
            title={`Tile ${tileId}`}
          >
            {tileId}
          </button>
        );
      })}
    </div>
  );
}

