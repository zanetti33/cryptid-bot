export function ModeSwitcher({
  mode,
  onChange,
  onAskAi,
  canAskAi = false,
  isBusy = false,
  isAskAiBusy = false,
}) {
  return (
    <div className="mode-switcher">
      <button
        className={mode === "structures" ? "active" : ""}
        onClick={() => onChange("structures")}
      >
        Structures
      </button>
      <button
        className={mode === "clues" ? "active" : ""}
        onClick={() => onChange("clues")}
      >
        Clues (round/cube)
      </button>
      <button onClick={onAskAi} disabled={!canAskAi || isBusy || isAskAiBusy}>
        {isAskAiBusy ? (
          <span className="button-with-spinner"><span className="loading-spinner" aria-hidden="true" />Ask AI</span>
        ) : "Ask AI"}
      </button>
    </div>
  );
}

