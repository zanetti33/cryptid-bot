import { useEffect, useMemo, useState } from "react";

import { postEndpoint } from "./api/client";
import { BoardComposer } from "./components/BoardComposer";
import { ClickableHexMap } from "./components/ClickableHexMap";
import { GameSetupForm } from "./components/GameSetupForm";
import { ModeSwitcher } from "./components/ModeSwitcher";
import { StructurePanel } from "./components/StructurePanel";
import { TokenPanel } from "./components/TokenPanel";
import { Toolbar } from "./components/Toolbar";

const DEFAULT_SESSION_ID = "default";
const ALL_PLAYER_IDS = ["alpha", "beta", "gamma", "omega", "epsilon"];
const DEFAULT_PLAYER_COUNT = 3;
const DEFAULT_BOARD_LAYOUT = [
  { slot_id: 1, section_id: "C", orientation: "normal" },
  { slot_id: 2, section_id: "A", orientation: "flipped" },
  { slot_id: 3, section_id: "F", orientation: "normal" },
  { slot_id: 4, section_id: "B", orientation: "normal" },
  { slot_id: 5, section_id: "E", orientation: "flipped" },
  { slot_id: 6, section_id: "D", orientation: "normal" },
];

function replacePlacement(placements, nextPlacement) {
  const filtered = placements.filter((entry) => entry.slot_id !== nextPlacement.slot_id);
  return [...filtered, nextPlacement].sort((left, right) => left.slot_id - right.slot_id);
}

function groupTokensByTile(observedTokens) {
  const byTile = new Map();
  for (const token of observedTokens || []) {
    const tileId = token?.tile_id;
    const playerId = token?.player_id;
    const tokenType = token?.token_type;
    if (typeof tileId !== "number" || !playerId || (tokenType !== "round" && tokenType !== "cube")) {
      continue;
    }

    if (!byTile.has(tileId)) {
      byTile.set(tileId, { round_tokens: [], cube_tokens: [] });
    }
    if (tokenType === "round") {
      byTile.get(tileId).round_tokens.push(playerId);
    } else {
      byTile.get(tileId).cube_tokens.push(playerId);
    }
  }
  return byTile;
}

function buildEnhancedTiles(baseTiles, structuresByTileId, observedTokens) {
  const tokenByTile = groupTokensByTile(observedTokens);
  return (baseTiles || []).map((tile) => {
    const structureOverride = structuresByTileId?.[String(tile.tile_id)] || structuresByTileId?.[tile.tile_id] || null;
    const tokenBundle = tokenByTile.get(tile.tile_id) || { round_tokens: [], cube_tokens: [] };

    return {
      ...tile,
      structure_type: structureOverride?.structure_type || tile.structure_type || null,
      structure_color: structureOverride?.structure_color || tile.structure_color || null,
      round_tokens: tokenBundle.round_tokens,
      cube_tokens: tokenBundle.cube_tokens,
      round_token_count: tokenBundle.round_tokens.length,
      cube_token_count: tokenBundle.cube_tokens.length,
    };
  });
}

export function App() {
  const [mode, setMode] = useState("structures");
  const [phase, setPhase] = useState("setup");
  const [selectedTileId, setSelectedTileId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [response, setResponse] = useState(null);
  const [boardCatalog, setBoardCatalog] = useState(null);
  const [clueCatalog, setClueCatalog] = useState([]);
  const [placements, setPlacements] = useState(DEFAULT_BOARD_LAYOUT);
  const [playerCount, setPlayerCount] = useState(DEFAULT_PLAYER_COUNT);
  const [turnOrder, setTurnOrder] = useState(ALL_PLAYER_IDS.slice(0, DEFAULT_PLAYER_COUNT));
  const [botPlayerId, setBotPlayerId] = useState(ALL_PLAYER_IDS[0]);
  const [botClueId, setBotClueId] = useState("");
  const [structureType, setStructureType] = useState("");
  const [structureColor, setStructureColor] = useState("");
  const [tokenPlayerId, setTokenPlayerId] = useState("");
  const [tokenType, setTokenType] = useState("");
  const [showAnimals, setShowAnimals] = useState(true);
  const [showStructures, setShowStructures] = useState(true);
  const [showTokens, setShowTokens] = useState(true);

  const warnings = useMemo(() => response?.warnings || [], [response]);
  const moves = useMemo(() => response?.data?.recommended_moves || [], [response]);
  const boardTiles = useMemo(() => response?.session?.board_layout_state?.board_tiles || [], [response]);
  const structuresByTileId = useMemo(() => response?.session?.structures_state?.by_tile_id || {}, [response]);
  const observedTokens = useMemo(() => response?.session?.map_state?.observed_tokens || [], [response]);
  const enhancedBoardTiles = useMemo(
    () => buildEnhancedTiles(boardTiles, structuresByTileId, observedTokens),
    [boardTiles, structuresByTileId, observedTokens],
  );
  const hasBoardLayout = useMemo(
    () => Boolean(response?.session?.board_layout_state?.is_complete && boardTiles.length),
    [response, boardTiles],
  );
  const configuredPlayerIds = useMemo(
    () => ALL_PLAYER_IDS.slice(0, playerCount),
    [playerCount],
  );
  const sessionBotPlayerId = response?.session?.setup?.bot_player_id || null;

  const isSetupValid =
    configuredPlayerIds.length === playerCount
    && Boolean(botPlayerId)
    && configuredPlayerIds.includes(botPlayerId)
    && turnOrder.length === playerCount
    && new Set(turnOrder).size === playerCount
    && turnOrder.every((playerId) => configuredPlayerIds.includes(playerId))
    && turnOrder.includes(botPlayerId)
    && Boolean(botClueId.trim());

  async function loadCatalog() {
    const catalog = await postEndpoint("/catalog", { session_id: DEFAULT_SESSION_ID });
    setBoardCatalog(catalog.data?.board_layout_catalog || null);
    setClueCatalog(catalog.data?.clues_catalog || []);
  }

  function updatePlayerCount(nextCount) {
    setPlayerCount(nextCount);
  }

  function updateTurnOrder(index, playerId) {
    if (!configuredPlayerIds.includes(playerId)) {
      return;
    }
    setTurnOrder((current) => {
      const base = configuredPlayerIds.map((defaultPlayer, position) => (
        configuredPlayerIds.includes(current[position]) ? current[position] : defaultPlayer
      ));
      const previousAtIndex = base[index];
      const duplicateIndex = base.findIndex((value, position) => position !== index && value === playerId);
      const next = [...base];
      next[index] = playerId;
      if (duplicateIndex >= 0) {
        next[duplicateIndex] = previousAtIndex;
      }
      return next;
    });
  }

  useEffect(() => {
    setBotPlayerId((current) => (configuredPlayerIds.includes(current) ? current : configuredPlayerIds[0] || ""));
    setTurnOrder((current) => {
      const filtered = current.filter((playerId) => configuredPlayerIds.includes(playerId));
      const missing = configuredPlayerIds.filter((playerId) => !filtered.includes(playerId));
      return [...filtered, ...missing];
    });
  }, [configuredPlayerIds]);

  useEffect(() => {
    let cancelled = false;

    async function loadCatalogOnMount() {
      try {
        const catalog = await postEndpoint("/catalog", { session_id: DEFAULT_SESSION_ID });
        if (cancelled) {
          return;
        }
        setBoardCatalog(catalog.data?.board_layout_catalog || null);
        setClueCatalog(catalog.data?.clues_catalog || []);
      } catch {
        if (!cancelled) {
          setClueCatalog([]);
        }
      }
    }

    loadCatalogOnMount();
    return () => {
      cancelled = true;
    };
  }, []);

  async function bootstrapSession() {
    if (!isSetupValid) {
      return;
    }

    setBusy(true);
    try {
      const setup = await postEndpoint("/setup", {
        session_id: DEFAULT_SESSION_ID,
        player_ids: configuredPlayerIds,
        turn_order: turnOrder,
        bot_player_id: botPlayerId,
        bot_clue_id: botClueId.trim(),
      });

      setBoardCatalog(setup.data?.board_layout_catalog || null);
      setClueCatalog(setup.data?.clues_catalog || clueCatalog);
      setPlacements(setup.data?.board_layout_catalog?.default_layout || DEFAULT_BOARD_LAYOUT);
      setResponse(setup);
      setPhase(setup.session.phase);
      setSelectedTileId(null);
    } finally {
      setBusy(false);
    }
  }

  function updatePlacement(slotId, fieldName, value) {
    const currentPlacement = placements.find((entry) => entry.slot_id === slotId) || {
      slot_id: slotId,
      section_id: "",
      orientation: "normal",
    };
    setPlacements(replacePlacement(placements, { ...currentPlacement, [fieldName]: value }));
  }

  async function applyBoardLayout() {
    setBusy(true);
    try {
      const result = await postEndpoint("/board-layout", {
        session_id: DEFAULT_SESSION_ID,
        placements,
      });
      setBoardCatalog(result.data?.board_layout_catalog || boardCatalog);
      setResponse(result);
      setPhase(result.session.phase);
      setSelectedTileId(null);
    } finally {
      setBusy(false);
    }
  }

  async function saveModeEntry() {
    if (selectedTileId === null || !hasBoardLayout) {
      return;
    }

    setBusy(true);
    try {
      if (mode === "structures") {
        if (!structureType || !structureColor) {
          return;
        }
        const result = await postEndpoint("/structures", {
          session_id: DEFAULT_SESSION_ID,
          structures: [
            {
              tile_id: selectedTileId,
              structure_type: structureType,
              structure_color: structureColor,
            },
          ],
        });
        setResponse(result);
        setPhase(result.session.phase);
      } else if (mode === "tokens") {
        if (!tokenPlayerId || !tokenType) {
          return;
        }
        const result = await postEndpoint("/map", {
          session_id: DEFAULT_SESSION_ID,
          observed_tokens: [
            ...observedTokens,
            {
              tile_id: selectedTileId,
              player_id: tokenPlayerId,
              token_type: tokenType,
            },
          ],
        });
        setResponse(result);
        setPhase(result.session.phase);
      } else {
        const result = await postEndpoint("/clues", {
          session_id: DEFAULT_SESSION_ID,
          by_player_id: {
            [sessionBotPlayerId || botPlayerId]: {
              notes: [`Selected tile ${selectedTileId}`],
            },
          },
        });
        setResponse(result);
        setPhase(result.session.phase);
      }
    } finally {
      setBusy(false);
    }
  }

  async function recalculate() {
    setBusy(true);
    try {
      const result = await postEndpoint("/recalculate", {
        session_id: DEFAULT_SESSION_ID,
        top_k: 5,
      });
      setResponse(result);
      setPhase(result.session.phase);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <h1>Cryptid SPA Recognition (MVP)</h1>

      <Toolbar
        phase={phase}
        onRecalculate={recalculate}
        isBusy={busy}
        hasBoardLayout={hasBoardLayout}
        showAnimals={showAnimals}
        showStructures={showStructures}
        showTokens={showTokens}
        onToggleAnimals={() => setShowAnimals((current) => !current)}
        onToggleStructures={() => setShowStructures((current) => !current)}
        onToggleTokens={() => setShowTokens((current) => !current)}
      />

      <GameSetupForm
        playerCount={playerCount}
        playerIds={configuredPlayerIds}
        turnOrder={turnOrder}
        botPlayerId={botPlayerId}
        botClueId={botClueId}
        clueCatalog={clueCatalog}
        isSetupValid={isSetupValid}
        isBusy={busy}
        onPlayerCountChange={updatePlayerCount}
        onTurnOrderChange={updateTurnOrder}
        onBotPlayerChange={setBotPlayerId}
        onBotClueChange={setBotClueId}
        onReloadCatalog={loadCatalog}
        onSubmit={bootstrapSession}
      />

      {(phase === "board_layout" || !hasBoardLayout) ? (
        <BoardComposer
          catalog={boardCatalog}
          placements={placements}
          onPlacementChange={updatePlacement}
          onApply={applyBoardLayout}
          isBusy={busy}
          isComplete={hasBoardLayout}
        />
      ) : null}

      {hasBoardLayout ? (
        <>
          <section className="panel-section">
            <div className="panel-header">
              <div>
                <h2>2. Rivedi la mappa</h2>
                <p>Ogni cella mostra il colore del proprio territorio. Seleziona un tile e poi salva una struttura o una clue.</p>
              </div>
            </div>

            <div className="terrain-legend">
              <span className="legend-chip forest">Forest</span>
              <span className="legend-chip mountain">Mountain</span>
              <span className="legend-chip water">Water</span>
              <span className="legend-chip desert">Desert</span>
              <span className="legend-chip swamp">Swamp</span>
              <span className="legend-chip overlay-animal">🐻/🐆 Animals</span>
              <span className="legend-chip overlay-structure">⬣/⌂ Structures</span>
              <span className="legend-chip overlay-token-round">● Round</span>
              <span className="legend-chip overlay-token-cube">■ Cube</span>
            </div>

            <ModeSwitcher mode={mode} onChange={setMode} />

            {selectedTileId === null ? (
              <p className="slot-meta">Seleziona una tile per inserire dati.</p>
            ) : null}

            {mode === "structures" ? (
              <StructurePanel
                structureType={structureType}
                structureColor={structureColor}
                isBusy={busy || selectedTileId === null}
                onStructureTypeChange={setStructureType}
                onStructureColorChange={setStructureColor}
                onSave={saveModeEntry}
              />
            ) : null}

            {mode === "tokens" ? (
              <TokenPanel
                playerIds={response?.session?.setup?.player_ids || configuredPlayerIds}
                tokenPlayerId={tokenPlayerId}
                tokenType={tokenType}
                isBusy={busy || selectedTileId === null}
                onTokenPlayerChange={setTokenPlayerId}
                onTokenTypeChange={setTokenType}
                onSave={saveModeEntry}
              />
            ) : null}

            {mode === "clues" ? (
              <div className="actions">
                <button onClick={saveModeEntry} disabled={busy || selectedTileId === null}>
                  Save Clue
                </button>
              </div>
            ) : null}

            <ClickableHexMap
              tiles={enhancedBoardTiles}
              selectedTileId={selectedTileId}
              onTileClick={setSelectedTileId}
              showAnimals={showAnimals}
              showStructures={showStructures}
              showTokens={showTokens}
            />
          </section>
        </>
      ) : null}

      <section>
        <h2>Warnings</h2>
        <pre>{JSON.stringify(warnings, null, 2)}</pre>
      </section>

      <section>
        <h2>Recommended Moves</h2>
        <pre>{JSON.stringify(moves, null, 2)}</pre>
      </section>
    </main>
  );
}

