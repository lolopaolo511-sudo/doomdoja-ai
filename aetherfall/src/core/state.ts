import type { GameState } from "./types";
import { SAVE_VERSION, TILE } from "./constants";
import { QUESTS } from "../data/quests";
import { STARTER_RECIPES } from "../data/recipes";

/** A fresh game. The player wakes at the village crossroads at morning. */
export function newGame(): GameState {
  const quests: GameState["quests"] = {};
  for (const id of Object.keys(QUESTS)) {
    quests[id] = { status: id === "letter" ? "locked" : "available", done: {} };
  }

  return {
    version: SAVE_VERSION,
    map: "village",
    player: { x: 14 * TILE + TILE / 2, y: 15 * TILE + TILE / 2 },
    clock: 8 * 60, // 08:00
    day: 1,
    inventory: {},
    quests,
    flags: {},
    collected: {},
    knownRecipes: [...STARTER_RECIPES],
  };
}

/** Deep clone used when starting/loading so saved/runtime state never alias. */
export function cloneState(s: GameState): GameState {
  return JSON.parse(JSON.stringify(s));
}
