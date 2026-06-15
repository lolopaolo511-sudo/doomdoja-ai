import type { GameState, MapData, Vec2 } from "../core/types";
import { TILE } from "../core/constants";
import { isTileSolid } from "../world/collision";

interface Node {
  x: number;
  y: number;
  g: number;
  f: number;
  parent: Node | null;
}

const key = (x: number, y: number) => y * 10000 + x;

/**
 * A* on the tile grid. Returns a list of pixel waypoints (tile centers) from
 * just after the start tile to the goal tile, or null if unreachable.
 */
export function findPath(
  map: MapData,
  state: GameState,
  from: Vec2,
  to: Vec2,
): Vec2[] | null {
  const sx = Math.floor(from.x / TILE);
  const sy = Math.floor(from.y / TILE);
  let gx = Math.floor(to.x / TILE);
  let gy = Math.floor(to.y / TILE);

  if (isTileSolid(map, gx, gy, state)) {
    const near = nearestWalkable(map, state, gx, gy);
    if (!near) return null;
    gx = near.x;
    gy = near.y;
  }
  if (sx === gx && sy === gy) return [{ x: to.x, y: to.y }];

  const open: Node[] = [];
  const came = new Map<number, Node>();
  const closed = new Set<number>();
  const h = (x: number, y: number) => Math.abs(x - gx) + Math.abs(y - gy);

  const start: Node = { x: sx, y: sy, g: 0, f: h(sx, sy), parent: null };
  open.push(start);
  came.set(key(sx, sy), start);

  const dirs = [
    [1, 0],
    [-1, 0],
    [0, 1],
    [0, -1],
  ];

  let guard = 0;
  while (open.length && guard++ < 6000) {
    // Pop lowest f.
    let bi = 0;
    for (let i = 1; i < open.length; i++) if (open[i].f < open[bi].f) bi = i;
    const cur = open.splice(bi, 1)[0];
    if (cur.x === gx && cur.y === gy) return reconstruct(cur);
    closed.add(key(cur.x, cur.y));

    for (const [dx, dy] of dirs) {
      const nx = cur.x + dx;
      const ny = cur.y + dy;
      const k = key(nx, ny);
      if (closed.has(k)) continue;
      if (isTileSolid(map, nx, ny, state)) continue;
      const g = cur.g + 1;
      const existing = came.get(k);
      if (existing && g >= existing.g) continue;
      const node: Node = { x: nx, y: ny, g, f: g + h(nx, ny), parent: cur };
      came.set(k, node);
      open.push(node);
    }
  }
  return null;
}

function reconstruct(end: Node): Vec2[] {
  const path: Vec2[] = [];
  let n: Node | null = end;
  while (n && n.parent) {
    path.push({ x: n.x * TILE + TILE / 2, y: n.y * TILE + TILE / 2 });
    n = n.parent;
  }
  path.reverse();
  return path;
}

function nearestWalkable(
  map: MapData,
  state: GameState,
  x: number,
  y: number,
): Vec2 | null {
  for (let r = 1; r <= 4; r++) {
    for (let dy = -r; dy <= r; dy++)
      for (let dx = -r; dx <= r; dx++) {
        if (Math.abs(dx) !== r && Math.abs(dy) !== r) continue;
        if (!isTileSolid(map, x + dx, y + dy, state)) return { x: x + dx, y: y + dy };
      }
  }
  return null;
}
