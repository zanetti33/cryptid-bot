export const DEFAULT_LAYOUT_SCENARIO = {
  scenario_id: "my-default-layout",
  description: "Boh",
  board: {
    kind: "placements",
    placements: [
      { slot_id: 1, section_id: "D", orientation: "flipped" },
      { slot_id: 2, section_id: "F", orientation: "flipped" },
      { slot_id: 3, section_id: "B", orientation: "normal" },
      { slot_id: 4, section_id: "C", orientation: "flipped" },
      { slot_id: 5, section_id: "A", orientation: "normal" },
      { slot_id: 6, section_id: "E", orientation: "normal" },
    ],
    structures: [
      {
        section_id: "D",
        local_id: 13,
        structure_type: "standing_stone",
        structure_color: "green",
      },
      {
        section_id: "F",
        local_id: 1,
        structure_type: "abandoned_shack",
        structure_color: "blue",
      },
      {
        section_id: "B",
        local_id: 1,
        structure_type: "abandoned_shack",
        structure_color: "green",
      },
      {
        section_id: "C",
        local_id: 12,
        structure_type: "standing_stone",
        structure_color: "white",
      },
      {
        section_id: "A",
        local_id: 9,
        structure_type: "standing_stone",
        structure_color: "blue",
      },
      {
        section_id: "E",
        local_id: 1,
        structure_type: "abandoned_shack",
        structure_color: "white",
      },
    ],
  },
  players: [
    {
      player_id: "bot",
      clue_id: "within_one_swamp",
    },
    {
      player_id: "p1",
      clue_id: "within_one_either_animal_territory",
    },
    {
      player_id: "p2",
      clue_id: "terrain_pair_desert_water",
    },
    {
      player_id: "p3",
      clue_id: "within_three_blue_structure",
    },
  ],
  turn_order: ["p1", "p2", "p3", "bot"],
  bot_player_id: "bot",
  include_inverse_clues: false,
  simulation: {
    seed: 17,
    observation_count: 12,
    include_bot_observations: true,
    ensure_player_polarity_coverage: true,
    distribution_mode: "equal_per_player",
  },
  evaluation: {
    top_k: 5,
  },
};


