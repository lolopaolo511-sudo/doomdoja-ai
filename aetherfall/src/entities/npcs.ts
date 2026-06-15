import type { MapId, Phase, DialogTree, Vec2 } from "../core/types";
import { TILE } from "../core/constants";
import { DIALOGS } from "../data/dialogs";

export interface Placement {
  map: MapId;
  /** Tile coords. */
  tx: number;
  ty: number;
}

/** A scheduled position, or `null` when the NPC is indoors/away this phase. */
export type Slot = Placement | null;

export interface NPCDef {
  id: string;
  name: string;
  title: string;
  /** Body + accent colors for the drawn sprite. */
  color: string;
  accent: string;
  dialog: DialogTree;
  /** Where the NPC stands during each phase of the day. */
  schedule: Record<Phase, Slot>;
}

/** Helper to build a same-spot schedule with optional overrides. */
function fixed(
  map: MapId,
  tx: number,
  ty: number,
  overrides: Partial<Record<Phase, Slot>> = {},
): Record<Phase, Slot> {
  const base: Placement = { map, tx, ty };
  return {
    dawn: base,
    day: base,
    dusk: base,
    night: base,
    ...overrides,
  };
}

export const NPCS: Record<string, NPCDef> = {
  mira: {
    id: "mira",
    name: "Mira",
    title: "Healer",
    color: "#6fb0a6",
    accent: "#e8f0ee",
    dialog: DIALOGS.mira,
    schedule: fixed("village", 11, 11, {
      dusk: { map: "village", tx: 7, ty: 18 },
      night: { map: "village", tx: 6, ty: 18 },
    }),
  },
  bertram: {
    id: "bertram",
    name: "Old Bertram",
    title: "Widower",
    color: "#9a8f7e",
    accent: "#d8cfc0",
    dialog: DIALOGS.bertram,
    schedule: fixed("village", 16, 11, {
      night: { map: "village", tx: 13, ty: 13 },
      dusk: { map: "village", tx: 14, ty: 13 },
    }),
  },
  garrin: {
    id: "garrin",
    name: "Garrin",
    title: "Carpenter",
    color: "#b9794a",
    accent: "#f0c78a",
    dialog: DIALOGS.garrin,
    schedule: fixed("village", 22, 20, {
      night: { map: "village", tx: 23, ty: 18 },
    }),
  },
  selene: {
    id: "selene",
    name: "Selene",
    title: "Scholar",
    color: "#7a6fb0",
    accent: "#cfc6f0",
    dialog: DIALOGS.selene,
    schedule: {
      dawn: { map: "ruins", tx: 12, ty: 16 },
      day: { map: "ruins", tx: 12, ty: 16 },
      dusk: { map: "ruins", tx: 14, ty: 11 },
      night: { map: "village", tx: 11, ty: 8 },
    },
  },
  caedry: {
    id: "caedry",
    name: "Caedry",
    title: "Hermit",
    color: "#6c7b86",
    accent: "#b8c6d0",
    dialog: DIALOGS.caedry,
    schedule: fixed("clearing", 18, 9, {
      day: { map: "clearing", tx: 16, ty: 9 },
    }),
  },
  pip: {
    id: "pip",
    name: "Pip",
    title: "Village child",
    color: "#d88a5a",
    accent: "#ffe0b0",
    dialog: DIALOGS.pip,
    schedule: {
      dawn: { map: "village", tx: 14, ty: 9 },
      day: { map: "village", tx: 17, ty: 9 },
      dusk: { map: "village", tx: 14, ty: 14 },
      night: { map: "village", tx: 10, ty: 12 },
    },
  },
  nan: {
    id: "nan",
    name: "Nan",
    title: "Village elder",
    color: "#a89db0",
    accent: "#e6dcec",
    dialog: DIALOGS.nan,
    schedule: {
      dawn: { map: "village", tx: 15, ty: 12 },
      day: { map: "village", tx: 15, ty: 12 },
      dusk: { map: "village", tx: 15, ty: 12 },
      night: null, // Nan sleeps; she's gone after dark.
    },
  },
  tomas: {
    id: "tomas",
    name: "Tomas",
    title: "Farmer",
    color: "#7e9a5a",
    accent: "#d6e6a8",
    dialog: DIALOGS.tomas,
    schedule: {
      dawn: { map: "village", tx: 19, ty: 9 },
      day: { map: "village", tx: 19, ty: 8 },
      dusk: { map: "village", tx: 18, ty: 12 },
      night: { map: "village", tx: 20, ty: 16 },
    },
  },
  wrenna: {
    id: "wrenna",
    name: "Wrenna",
    title: "Herbalist",
    color: "#5a9a6e",
    accent: "#bff0c8",
    dialog: DIALOGS.wrenna,
    schedule: {
      dawn: { map: "forest", tx: 5, ty: 11 },
      day: { map: "forest", tx: 9, ty: 11 },
      dusk: { map: "forest", tx: 15, ty: 11 },
      night: { map: "forest", tx: 20, ty: 11 },
    },
  },
};

/** Pixel-center position of an NPC's slot, or null if away. */
export function slotPos(slot: Slot): Vec2 | null {
  if (!slot) return null;
  return { x: slot.tx * TILE + TILE / 2, y: slot.ty * TILE + TILE / 2 };
}

export const NPC_LIST = Object.values(NPCS);
