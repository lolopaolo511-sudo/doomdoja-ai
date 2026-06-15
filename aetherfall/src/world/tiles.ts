import type { TileKind } from "../core/types";

/** Which tiles block movement. */
export const SOLID: Record<TileKind, boolean> = {
  grass: false,
  grass2: false,
  path: false,
  water: true,
  tree: true,
  rock: true,
  wall: true,
  floor: false,
  flower: false,
  bush: true,
  sand: false,
  ruinFloor: false,
  ruinWall: true,
  mist: false,
  bridge: false,
};

/** Base colors for each tile, used by the painterly renderer. */
export const TILE_COLOR: Record<TileKind, string> = {
  grass: "#4a7a4e",
  grass2: "#427046",
  path: "#9c8762",
  water: "#2f6f9e",
  tree: "#2c5a39",
  rock: "#6b6f7a",
  wall: "#7c6b56",
  floor: "#b09b73",
  flower: "#4a7a4e",
  bush: "#356b3f",
  sand: "#c9b787",
  ruinFloor: "#8c8a86",
  ruinWall: "#5d5b58",
  mist: "#6f7e8c",
  bridge: "#9c7b4e",
};
