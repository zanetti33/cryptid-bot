"""Decision-making utilities for Cryptid bot."""

from ai.engine import CryptidAIEngine
from ai.knowledge_update import KnowledgeTracker, KnowledgeUpdateResult
from ai.scenario_harness import (
	RecommendedMoveTruth,
	ScenarioBoardSpec,
	ScenarioDefinition,
	ScenarioEvaluationConfig,
	ScenarioEvaluationResult,
	ScenarioPlayer,
	ScenarioSimulationConfig,
	SyntheticObservation,
	build_board_for_scenario,
	evaluate_scenario,
	evaluate_scenario_file,
	format_evaluation_report,
	generate_synthetic_observations,
	load_scenario_definition,
	scenario_definition_from_dict,
)
from ai.types import AICubePlacement, AIDebugState, AIMove, AIResponse, InitialSetup, ObservationRecord
from ai.inference import HypothesisSpace, PlayerHypothesisSpace, infer_hypothesis_space
from ai.strategy import RecommendedMove, recommend_moves

__all__ = [
	"CryptidAIEngine",
	"KnowledgeTracker",
	"KnowledgeUpdateResult",
	"RecommendedMoveTruth",
	"AIDebugState",
	"AIMove",
	"AIResponse",
	"AICubePlacement",
	"InitialSetup",
	"ObservationRecord",
	"ScenarioBoardSpec",
	"ScenarioDefinition",
	"ScenarioEvaluationConfig",
	"ScenarioEvaluationResult",
	"ScenarioPlayer",
	"ScenarioSimulationConfig",
	"SyntheticObservation",
	"HypothesisSpace",
	"PlayerHypothesisSpace",
	"build_board_for_scenario",
	"evaluate_scenario",
	"evaluate_scenario_file",
	"format_evaluation_report",
	"generate_synthetic_observations",
	"infer_hypothesis_space",
	"load_scenario_definition",
	"RecommendedMove",
	"recommend_moves",
	"scenario_definition_from_dict",
]

