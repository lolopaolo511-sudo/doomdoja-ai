import type { GameState, MapData } from "../core/types";
import { SOLID } from "./tiles";

/** Whether a tile blocks movement, accounting for the repairable bridge. */
export function isTileSolid(
  map: MapData,
  tx: number,
  ty: number,
  state: GameState,
): boolean {
  if (tx < 0 || ty < 0 || tx >= map.cols || ty >= map.rows) return true;
  const kind = map.tiles[ty][tx];
  if (kind === "bridge") return !state.flags.bridgeRepaired;
  return SOLID[kind];
}

/** Axis-aligned box (pixel coords) vs solid tiles on the map. */
export function boxCollides(
  map: MapData,
  state: GameState,
  cx: number,
  cy: number,
  halfW: number,
  halfH: number,
  tile: number,
): boolean {
  const minX = Math.floor((cx - halfW) / tile);
  const maxX = Math.floor((cx + halfW - 0.001) / tile);
  const minY = Math.floor((cy - halfH) / tile);
  const maxY = Math.floor((cy + halfH - 0.001) / tile);
  for (let ty = minY; ty <= maxY; ty++)
    for (let tx = minX; tx <= maxX; tx++)
      if (isTileSolid(map, tx, ty, state)) return true;
  return false;
}
