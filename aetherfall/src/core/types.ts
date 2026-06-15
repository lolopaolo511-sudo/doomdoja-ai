// ---------------------------------------------------------------------------
// Shared types for the whole game. Keep this dependency-free.
// ---------------------------------------------------------------------------

export interface Vec2 {
  x: number;
  y: number;
}

/** Time-of-day phases derived from the world clock. */
export type Phase = "dawn" | "day" | "dusk" | "night";

/** A location the player can be in. */
export type MapId = "village" | "forest" | "ruins" | "clearing";

/** Tile types used by the tilemap renderer + collision. */
export type TileKind =
  | "grass"
  | "grass2"
  | "path"
  | "water"
  | "tree"
  | "rock"
  | "wall"
  | "floor"
  | "flower"
  | "bush"
  | "sand"
  | "ruinFloor"
  | "ruinWall"
  | "mist"
  | "bridge";

export interface TileDef {
  kind: TileKind;
  solid: boolean;
}

/** A doorway/edge that moves the player to another map. */
export interface Portal {
  /** Tile rect (in tile coords) that triggers the portal. */
  x: number;
  y: number;
  w: number;
  h: number;
  to: MapId;
  /** Spawn tile in the destination map. */
  spawn: Vec2;
  label: string;
}

/** A decorative or interactable object placed in the world (pixel coords). */
export interface WorldObject {
  id: string;
  kind: "sign" | "chest" | "well" | "campfire" | "lantern" | "shrine" | "herb" | "crystal" | "mushroom";
  x: number;
  y: number;
  /** Optional interaction text / behaviour key. */
  text?: string;
  /** Item granted when collected (for gatherable objects). */
  gives?: string;
  /** Quest item flag id consumed once collected. */
  once?: boolean;
}

export interface MapData {
  id: MapId;
  name: string;
  /** Width/height in tiles. */
  cols: number;
  rows: number;
  /** Row-major tile grid. */
  tiles: TileKind[][];
  portals: Portal[];
  objects: WorldObject[];
  /** Ambient base color used as canvas clear (before lighting tint). */
  ambient: string;
}

// ---------------------------------------------------------------------------
// Items / inventory / crafting
// ---------------------------------------------------------------------------

export interface ItemDef {
  id: string;
  name: string;
  desc: string;
  /** Emoji-ish glyph drawn in the inventory grid. */
  glyph: string;
  color: string;
  stackable: boolean;
}

export interface Recipe {
  id: string;
  result: string;
  resultCount: number;
  /** itemId -> count required. */
  inputs: Record<string, number>;
  name: string;
  desc: string;
}

// ---------------------------------------------------------------------------
// Quests
// ---------------------------------------------------------------------------

export type QuestStatus = "locked" | "available" | "active" | "complete";

export interface QuestObjective {
  id: string;
  text: string;
}

export interface QuestDef {
  id: string;
  title: string;
  giver: string;
  summary: string;
  objectives: QuestObjective[];
  /** Items rewarded on completion. itemId -> count. */
  reward: Record<string, number>;
  /** Optional follow-up quest unlocked on completion. */
  unlocks?: string;
}

// ---------------------------------------------------------------------------
// Dialog
// ---------------------------------------------------------------------------

export interface DialogChoice {
  text: string;
  /** Next node id, or null to end the conversation. */
  next?: string | null;
  /** Only show this choice if the predicate passes. */
  cond?: (s: GameState) => boolean;
  /** Side-effect run when the choice is picked. */
  effect?: (ctx: DialogContext) => void;
}

export interface DialogNode {
  id: string;
  /** Spoken line(s). A function lets dialog react to state / time. */
  text: string | ((s: GameState) => string);
  choices?: DialogChoice[];
  /** If set, jump straight to this node id (no choices shown). */
  next?: string | null;
}

export interface DialogTree {
  /** Pick the entry node based on current state. */
  start: (s: GameState) => string;
  nodes: Record<string, DialogNode>;
}

/** Passed to dialog effects so they can mutate the world safely. */
export interface DialogContext {
  state: GameState;
  give: (itemId: string, n?: number) => void;
  take: (itemId: string, n?: number) => boolean;
  has: (itemId: string, n?: number) => boolean;
  startQuest: (id: string) => void;
  completeQuest: (id: string) => void;
  setObjective: (questId: string, objId: string) => void;
  setFlag: (key: string, value?: boolean | number | string) => void;
  flag: (key: string) => boolean | number | string | undefined;
  toast: (msg: string) => void;
}

// ---------------------------------------------------------------------------
// Persistent game state (everything in here is saved to localStorage)
// ---------------------------------------------------------------------------

export interface QuestState {
  status: QuestStatus;
  /** objectiveId -> done. */
  done: Record<string, boolean>;
}

export interface GameState {
  /** Schema version for save migration. */
  version: number;
  map: MapId;
  player: Vec2;
  /** Minutes since dawn of day 1. World clock. */
  clock: number;
  day: number;
  inventory: Record<string, number>;
  quests: Record<string, QuestState>;
  /** Arbitrary story flags (talked-to, doors opened, choices made, …). */
  flags: Record<string, boolean | number | string>;
  /** Objects already collected (so they don't respawn). */
  collected: Record<string, boolean>;
  /** Crafting recipes the player has unlocked. */
  knownRecipes: string[];
}
