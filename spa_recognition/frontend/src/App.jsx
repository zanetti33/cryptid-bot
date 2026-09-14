import { useEffect, useMemo, useRef, useState } from "react";

import { postEndpoint } from "./api/client";
import { ClickableHexMap } from "./components/ClickableHexMap";
import { DEFAULT_LAYOUT_SCENARIO } from "./defaultLayoutScenario";
import { GameSetupForm } from "./components/GameSetupForm";
import { ModeSwitcher } from "./components/ModeSwitcher";
import { StructurePanel } from "./components/StructurePanel";
import { TokenPanel } from "./components/TokenPanel";
import { Toolbar } from "./components/Toolbar";

const DEFAULT_SESSION_ID = "default";
const ALL_PLAYER_IDS = ["bot", "p1", "p2", "p3", "p4"];
const DEFAULT_PLAYER_COUNT = DEFAULT_LAYOUT_SCENARIO.players.length;
const DEFAULT_BOARD_LAYOUT = DEFAULT_LAYOUT_SCENARIO.board.placements;

function replacePlacement(placements, nextPlacement) {
  const filtered = placements.filter((entry) => entry.slot_id !== nextPlacement.slot_id);
  return [...filtered, nextPlacement].sort((left, right) => left.slot_id - right.slot_id);
}

function groupCluesByTile(placedClues) {
  const byTile = new Map();
  for (const clue of placedClues || []) {
    const tileId = clue?.tile_id;
    const playerId = clue?.player_id;
    const tokenType = clue?.token_type;
    if (typeof tileId !== "number" || !playerId || (tokenType !== "round" && tokenType !== "cube")) {
      continue;
    }

    if (!byTile.has(tileId)) {
      byTile.set(tileId, new Map());
    }
    byTile.get(tileId).set(playerId, tokenType);
  }

  const normalizedByTile = new Map();
  for (const [tileId, playersMap] of byTile.entries()) {
    const roundTokens = [];
    const cubeTokens = [];
    for (const [playerId, normalizedType] of playersMap.entries()) {
      if (normalizedType === "round") {
        roundTokens.push(playerId);
      } else {
        cubeTokens.push(playerId);
      }
    }
    normalizedByTile.set(tileId, { round_tokens: roundTokens, cube_tokens: cubeTokens });
  }

  return normalizedByTile;
}

function buildPlayerLabelsById(playerIds) {
  return (playerIds || []).reduce((acc, playerId, index) => {
    acc[playerId] = String(index + 1);
    return acc;
  }, {});
}

function buildEnhancedTiles(baseTiles, structuresByTileId, observedTokens) {
  const tokenByTile = groupCluesByTile(observedTokens);
  return (baseTiles || []).map((tile) => {
    const hasStringKey = structuresByTileId?.[String(tile.tile_id)] !== undefined;
    const hasNumericKey = structuresByTileId?.[tile.tile_id] !== undefined;
    const hasStructureOverride = hasStringKey || hasNumericKey;
    const structureOverride = hasStringKey
      ? structuresByTileId[String(tile.tile_id)]
      : structuresByTileId?.[tile.tile_id];
    const tokenBundle = tokenByTile.get(tile.tile_id) || { round_tokens: [], cube_tokens: [] };

    return {
      ...tile,
      structure_type: hasStructureOverride
        ? (structureOverride?.structure_type ?? null)
        : (tile.structure_type || null),
      structure_color: hasStructureOverride
        ? (structureOverride?.structure_color ?? null)
        : (tile.structure_color || null),
      round_tokens: tokenBundle.round_tokens,
      cube_tokens: tokenBundle.cube_tokens,
      round_token_count: tokenBundle.round_tokens.length,
      cube_token_count: tokenBundle.cube_tokens.length,
    };
  });
}

function formatTime(value) {
  if (!value) {
    return "-";
  }
  return value.toLocaleTimeString("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function sectionLocalKey(sectionId, localId) {
  return `${sectionId}:${localId}`;
}

function mapScenarioStructuresToTileStructures(boardTiles, scenarioStructures) {
  const tileIdBySectionLocal = new Map();
  for (const tile of boardTiles || []) {
    const sectionId = tile?.section_id;
    const localId = tile?.local_id;
    const tileId = tile?.tile_id;
    if (typeof sectionId === "string" && typeof localId === "number" && typeof tileId === "number") {
      tileIdBySectionLocal.set(sectionLocalKey(sectionId, localId), tileId);
    }
  }

  const mappedStructures = [];
  const missingStructures = [];
  for (const structure of scenarioStructures || []) {
    const key = sectionLocalKey(structure?.section_id, structure?.local_id);
    const tileId = tileIdBySectionLocal.get(key);
    if (typeof tileId !== "number") {
      missingStructures.push(structure);
      continue;
    }
    mappedStructures.push({
      tile_id: tileId,
      structure_type: structure.structure_type,
      structure_color: structure.structure_color,
    });
  }

  return { mappedStructures, missingStructures };
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
  const [includeInverseClues, setIncludeInverseClues] = useState(false);
  const [structureType, setStructureType] = useState("");
  const [structureColor, setStructureColor] = useState("");
  const [tokenPlayerId, setTokenPlayerId] = useState("");
  const [tokenType, setTokenType] = useState("");
  const [showAnimals, setShowAnimals] = useState(true);
  const [showStructures, setShowStructures] = useState(true);
  const [showTokens, setShowTokens] = useState(true);
  const [aiBusyAction, setAiBusyAction] = useState(null);
  const [warningToast, setWarningToast] = useState(null);
  const [lastAiSyncAt, setLastAiSyncAt] = useState(null);
  const [initializing, setInitializing] = useState(true);
  const aiSyncTimerRef = useRef(null);

  const warnings = useMemo(() => response?.warnings || [], [response]);
  const moves = useMemo(() => response?.data?.recommended_moves || [], [response]);
  const latestWarning = useMemo(
    () => (warnings.length ? warnings[warnings.length - 1] : null),
    [warnings],
  );
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
  const availablePlayerIds = useMemo(
    () => response?.session?.setup?.player_ids || configuredPlayerIds,
    [response, configuredPlayerIds],
  );
  const playerLabelsById = useMemo(
    () => buildPlayerLabelsById(availablePlayerIds),
    [availablePlayerIds],
  );
  useEffect(() => {
    const candidates = availablePlayerIds;
    setTokenPlayerId((current) => (candidates.includes(current) ? current : ""));
  }, [availablePlayerIds]);

  useEffect(() => {
    if (!latestWarning) {
      return;
    }
    setWarningToast(latestWarning);
    const timeoutId = setTimeout(() => {
      setWarningToast(null);
    }, 4000);
    return () => clearTimeout(timeoutId);
  }, [latestWarning?.code, latestWarning?.message, latestWarning?.severity]);

  useEffect(() => (
    () => {
      if (aiSyncTimerRef.current) {
        clearTimeout(aiSyncTimerRef.current);
      }
    }
  ), []);

  function updatePlayerCount(nextCount) {
    setPlayerCount(nextCount);
  }

  function updateIncludeInverseClues(nextValue) {
    setIncludeInverseClues(nextValue);
    if (!nextValue) {
      setBotClueId((current) => (current.startsWith("not_") ? "" : current));
    }
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
      } finally {
        if (!cancelled) {
          setInitializing(false);
        }
      }
    }

    loadCatalogOnMount();
    return () => {
      cancelled = true;
    };
  }, []);

  async function bootstrapSession(overrides = null) {
    const selectedPlayers = overrides?.player_ids || configuredPlayerIds;
    const selectedTurnOrder = overrides?.turn_order || turnOrder;
    const selectedBotPlayerId = overrides?.bot_player_id || botPlayerId;
    const selectedBotClueId = (overrides?.bot_clue_id || botClueId).trim();
    const selectedPlacements = overrides?.placements || placements;
    const selectedIncludeInverseClues = overrides?.include_inverse_clues ?? includeInverseClues;
    const isValidRequest =
      selectedPlayers.length > 0
      && Boolean(selectedBotPlayerId)
      && selectedPlayers.includes(selectedBotPlayerId)
      && selectedTurnOrder.length === selectedPlayers.length
      && new Set(selectedTurnOrder).size === selectedPlayers.length
      && selectedTurnOrder.every((playerId) => selectedPlayers.includes(playerId))
      && selectedTurnOrder.includes(selectedBotPlayerId)
      && Boolean(selectedBotClueId);
    if (!isValidRequest) {
      return;
    }

    setBusy(true);
    try {
      const setup = await postEndpoint("/setup", {
        session_id: DEFAULT_SESSION_ID,
        player_ids: selectedPlayers,
        turn_order: selectedTurnOrder,
        bot_player_id: selectedBotPlayerId,
        bot_clue_id: selectedBotClueId,
        include_inverse_clues: selectedIncludeInverseClues,
      });

      setBoardCatalog(setup.data?.board_layout_catalog || null);
      setClueCatalog(setup.data?.clues_catalog || clueCatalog);
      setPlacements(selectedPlacements);
      setResponse(setup);
      setPhase(setup.session.phase);
      setSelectedTileId(null);
      return setup;
    } finally {
      setBusy(false);
    }
  }

  async function applyDefaultSetup() {
    const defaultPlayerIds = DEFAULT_LAYOUT_SCENARIO.players.map((player) => player.player_id);
    const defaultBotPlayerId = DEFAULT_LAYOUT_SCENARIO.bot_player_id;
    const defaultBotClueId = (
      DEFAULT_LAYOUT_SCENARIO.players.find((player) => player.player_id === defaultBotPlayerId)?.clue_id || ""
    );
    const defaultTurnOrder = DEFAULT_LAYOUT_SCENARIO.turn_order;
    const defaultPlacements = DEFAULT_LAYOUT_SCENARIO.board.placements;
    const defaultStructures = DEFAULT_LAYOUT_SCENARIO.board.structures;
    const defaultSimulation = DEFAULT_LAYOUT_SCENARIO.simulation || {};
    const defaultIncludeInverseClues = Boolean(DEFAULT_LAYOUT_SCENARIO.include_inverse_clues);

    setPlayerCount(defaultPlayerIds.length);
    setTurnOrder(defaultTurnOrder);
    setBotPlayerId(defaultBotPlayerId);
    setBotClueId(defaultBotClueId);
    setPlacements(defaultPlacements);
    setIncludeInverseClues(defaultIncludeInverseClues);

    try {
      await bootstrapSession({
        player_ids: defaultPlayerIds,
        turn_order: defaultTurnOrder,
        bot_player_id: defaultBotPlayerId,
        bot_clue_id: defaultBotClueId,
        placements: defaultPlacements,
        include_inverse_clues: defaultIncludeInverseClues,
      });
      const boardLayoutResult = await applyBoardLayoutWithPlacements(defaultPlacements);
      const boardTilesFromLayout = boardLayoutResult?.session?.board_layout_state?.board_tiles || [];
      const { mappedStructures, missingStructures } = mapScenarioStructuresToTileStructures(
        boardTilesFromLayout,
        defaultStructures,
      );

      if (mappedStructures.length > 0) {
        setBusy(true);
        try {
          const structuresResult = await postEndpoint("/structures", {
            session_id: DEFAULT_SESSION_ID,
            structures: mappedStructures,
          });
          setResponse(structuresResult);
          setPhase(structuresResult.session.phase);
          scheduleAiSync();
        } finally {
          setBusy(false);
        }
      }

      if (missingStructures.length > 0) {
        setWarningToast({
          code: "DEFAULT_LAYOUT_STRUCTURES_PARTIAL",
          message: `${missingStructures.length} strutture non applicate: tile non trovato nel layout corrente.`,
          severity: "warn",
        });
      }

      const simulationResult = await postEndpoint("/simulate-observations", {
        session_id: DEFAULT_SESSION_ID,
        player_clues: DEFAULT_LAYOUT_SCENARIO.players,
        observation_count: defaultSimulation.observation_count,
        include_bot_observations: defaultSimulation.include_bot_observations,
        ensure_player_polarity_coverage: defaultSimulation.ensure_player_polarity_coverage,
        distribution_mode: defaultSimulation.distribution_mode,
      });
      setResponse(simulationResult);
      setPhase(simulationResult.session.phase);
      scheduleAiSync();
    } catch (error) {
      setWarningToast({
        code: "DEFAULT_LAYOUT_APPLY_FAILED",
        message: error instanceof Error ? error.message : "Applicazione layout default fallita.",
        severity: "error",
      });
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

  async function applyBoardLayoutWithPlacements(layoutPlacements) {
    setBusy(true);
    try {
      const result = await postEndpoint("/board-layout", {
        session_id: DEFAULT_SESSION_ID,
        placements: layoutPlacements,
        layout_mode: "manual",
      });
      setBoardCatalog(result.data?.board_layout_catalog || boardCatalog);
      setResponse(result);
      setPhase(result.session.phase);
      setSelectedTileId(null);
      return result;
    } finally {
      setBusy(false);
    }
  }

  async function applyBoardLayout() {
    await applyBoardLayoutWithPlacements(placements);
  }

  async function askAiForTile() {
    if (selectedTileId === null || !hasBoardLayout || !tokenPlayerId) {
      return;
    }

    setBusy(true);
    setAiBusyAction("ask_ai");
    try {
      const result = await postEndpoint("/ask-ai", {
        session_id: DEFAULT_SESSION_ID,
        tile_id: selectedTileId,
        player_id: tokenPlayerId,
      });
      setTokenType(result.data?.token_type || "");
      setResponse(result);
      setPhase(result.session.phase);
      scheduleAiSync();
    } finally {
      setBusy(false);
      setAiBusyAction((current) => (current === "ask_ai" ? null : current));
    }
  }

  function scheduleAiSync() {
    if (!hasBoardLayout) {
      return;
    }
    if (aiSyncTimerRef.current) {
      clearTimeout(aiSyncTimerRef.current);
    }
    aiSyncTimerRef.current = setTimeout(() => {
      void recalculate({ background: true });
    }, 350);
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
        scheduleAiSync();
      } else if (mode === "clues") {
        if (!tokenPlayerId || !tokenType) {
          return;
        }
        const nextObservedTokens = [
          ...observedTokens.filter((entry) => !(
            entry?.tile_id === selectedTileId
            && entry?.player_id === tokenPlayerId
          )),
          {
            tile_id: selectedTileId,
            player_id: tokenPlayerId,
            token_type: tokenType,
          },
        ];
        const result = await postEndpoint("/map", {
          session_id: DEFAULT_SESSION_ID,
          observed_tokens: nextObservedTokens,
        });
        setResponse(result);
        setPhase(result.session.phase);
        scheduleAiSync();
      }
    } finally {
      setBusy(false);
    }
  }

  async function removeStructureEntry() {
    if (selectedTileId === null || !hasBoardLayout) {
      return;
    }

    setBusy(true);
    try {
      const result = await postEndpoint("/structures", {
        session_id: DEFAULT_SESSION_ID,
        structures: [
          {
            tile_id: selectedTileId,
            remove: true,
          },
        ],
      });
      setResponse(result);
      setPhase(result.session.phase);
      scheduleAiSync();
    } finally {
      setBusy(false);
    }
  }

  async function removeClueEntry() {
    if (selectedTileId === null || !hasBoardLayout || !tokenPlayerId) {
      return;
    }

    setBusy(true);
    try {
      const filtered = observedTokens.filter((entry) => !(
        entry?.tile_id === selectedTileId
        && entry?.player_id === tokenPlayerId
      ));

      const result = await postEndpoint("/map", {
        session_id: DEFAULT_SESSION_ID,
        observed_tokens: filtered,
      });
      setResponse(result);
      setPhase(result.session.phase);
      scheduleAiSync();
    } finally {
      setBusy(false);
    }
  }

  async function recalculate(options = { background: false }) {
    const isBackground = Boolean(options?.background);
    if (!isBackground) {
      setBusy(true);
      setAiBusyAction("recalculate");
    } else {
      setAiBusyAction((current) => (current ? current : "autosync"));
    }
    try {
      const result = await postEndpoint("/recalculate", {
        session_id: DEFAULT_SESSION_ID,
        top_k: 5,
      });
      setResponse(result);
      setPhase(result.session.phase);
      setLastAiSyncAt(new Date());
    } catch (error) {
      setWarningToast({
        code: "AI_RECALCULATE_REQUEST_FAILED",
        message: error instanceof Error ? error.message : "Recalculate AI request failed.",
        severity: "error",
      });
    } finally {
      if (!isBackground) {
        setBusy(false);
        setAiBusyAction((current) => (current === "recalculate" ? null : current));
      } else {
        setAiBusyAction((current) => (current === "autosync" ? null : current));
      }
    }
  }

  return (
    <main className="app-shell">
      <div className="app-title-row">
        <h1>Cryptid SPA Recognition (MVP)</h1>
        <button
          type="button"
          onClick={applyDefaultSetup}
          disabled={busy}
          aria-label="Setup partita"
          title="Setup partita"
        >
          {busy ? "Configurazione..." : "Applica layout default"}
        </button>
      </div>

      {initializing ? (
        <div className="app-init-banner" role="status">
          Inizializzazione ambiente in corso...
        </div>
      ) : null}

      <Toolbar
        phase={phase}
        hasBoardLayout={hasBoardLayout}
        showAnimals={showAnimals}
        showStructures={showStructures}
        showTokens={showTokens}
        onToggleAnimals={() => setShowAnimals((current) => !current)}
        onToggleStructures={() => setShowStructures((current) => !current)}
        onToggleTokens={() => setShowTokens((current) => !current)}
      />

      {!hasBoardLayout ? (
        <GameSetupForm
          playerCount={playerCount}
          playerIds={configuredPlayerIds}
          turnOrder={turnOrder}
          botPlayerId={botPlayerId}
          botClueId={botClueId}
          clueCatalog={clueCatalog}
          includeInverseClues={includeInverseClues}
          isBusy={busy}
          onPlayerCountChange={updatePlayerCount}
          onTurnOrderChange={updateTurnOrder}
          onBotPlayerChange={setBotPlayerId}
          onBotClueChange={setBotClueId}
          onIncludeInverseCluesChange={updateIncludeInverseClues}
          boardCatalog={boardCatalog}
          placements={placements}
          onPlacementChange={updatePlacement}
          onApplyBoardLayout={applyBoardLayout}
          isBoardLayoutComplete={hasBoardLayout}
        />
      ) : null}

      {hasBoardLayout ? (
        <>
          <section className="panel-section">
            <div className="panel-header">
              <div>
                <h2>2. Rivedi la mappa</h2>
                <p>Ogni cella mostra il colore del proprio territorio. Seleziona un tile e poi salva/rimuovi una struttura o una clue (round/cube).</p>
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
              <span className="legend-chip overlay-token-round">● Round clue (numero giocatore)</span>
              <span className="legend-chip overlay-token-cube">■ Cube clue (numero giocatore)</span>
            </div>

            <ModeSwitcher
              mode={mode}
              onChange={setMode}
              onAskAi={askAiForTile}
              canAskAi={selectedTileId !== null && mode === "clues" && Boolean(tokenPlayerId)}
              isBusy={busy}
              isAskAiBusy={aiBusyAction === "ask_ai"}
            />

            {aiBusyAction === "autosync" ? (
              <p className="slot-meta ai-status-inline">
                <span className="loading-spinner" aria-hidden="true" />
                Aggiornamento AI in corso...
              </p>
            ) : null}

            <p className="slot-meta">
              Ultima sincronizzazione AI: {formatTime(lastAiSyncAt)}
            </p>

            {selectedTileId === null ? (
              <p className="slot-meta">Seleziona una tile per inserire dati.</p>
            ) : null}

            {mode === "structures" ? (
              <StructurePanel
                structureType={structureType}
                structureColor={structureColor}
                isBusy={busy}
                hasSelection={selectedTileId !== null}
                onStructureTypeChange={setStructureType}
                onStructureColorChange={setStructureColor}
                onSave={saveModeEntry}
                onRemove={removeStructureEntry}
              />
            ) : null}

            {mode === "clues" ? (
              <TokenPanel
                playerIds={availablePlayerIds}
                tokenPlayerId={tokenPlayerId}
                tokenType={tokenType}
                isBusy={busy}
                hasSelection={selectedTileId !== null}
                onTokenPlayerChange={setTokenPlayerId}
                onTokenTypeChange={setTokenType}
                onSave={saveModeEntry}
                onRemove={removeClueEntry}
              />
            ) : null}

            <ClickableHexMap
              tiles={enhancedBoardTiles}
              playerLabelsById={playerLabelsById}
              selectedTileId={selectedTileId}
              onTileClick={setSelectedTileId}
              showAnimals={showAnimals}
              showStructures={showStructures}
              showTokens={showTokens}
            />
          </section>
        </>
      ) : null}

      {warningToast ? (
        <div className={`warning-toast warning-${warningToast.severity || "warn"}`} role="status" aria-live="polite">
          <strong>{warningToast.code}</strong>: {warningToast.message}
        </div>
      ) : null}

      <section>
        <div className="panel-header">
          <div>
            <h2>Recommended Moves</h2>
            <p className="slot-meta">Ultimo ricalcolo AI: {formatTime(lastAiSyncAt)}</p>
          </div>
          <button onClick={() => recalculate()} disabled={!hasBoardLayout || busy || aiBusyAction === "recalculate"}>
            {aiBusyAction === "recalculate" ? (
              <span className="button-with-spinner"><span className="loading-spinner" aria-hidden="true" />Recalculate AI</span>
            ) : "Recalculate AI"}
          </button>
        </div>
        <pre>{JSON.stringify(moves, null, 2)}</pre>
      </section>
    </main>
  );
}

