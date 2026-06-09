export function Toolbar({ phase, onRecalculate, isBusy }) {
  return (
    <div className="toolbar">
      <span>Phase: {phase}</span>
      <button onClick={onRecalculate} disabled={isBusy}>
        {isBusy ? "Recalculating..." : "Recalculate AI"}
      </button>
    </div>
  );
}

