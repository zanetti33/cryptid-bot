export function ModeSwitcher({ mode, onChange }) {
  return (
    <div className="mode-switcher">
      <button
        className={mode === "structures" ? "active" : ""}
        onClick={() => onChange("structures")}
      >
        Structures
      </button>
      <button
        className={mode === "tokens" ? "active" : ""}
        onClick={() => onChange("tokens")}
      >
        Tokens
      </button>
      <button
        className={mode === "clues" ? "active" : ""}
        onClick={() => onChange("clues")}
      >
        Clues
      </button>
    </div>
  );
}

