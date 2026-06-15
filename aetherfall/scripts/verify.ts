// Connectivity + economy sanity checks. Bundled with esbuild, run with node.
import { getMaps, getMap } from "../src/world/maps";
import { isTileSolid } from "../src/world/collision";
import { newGame } from "../src/core/state";
import { TILE } from "../src/core/constants";
import { NPC_LIST } from "../src/entities/npcs";
import type { GameState, MapData, Vec2 } from "../src/core/types";

let failures = 0;
const fail = (m: string) => {
  console.error("  ✗ " + m);
  failures++;
};
const ok = (m: string) => console.log("  ✓ " + m);

function flood(map: MapData, state: GameState, start: Vec2): Set<number> {
  const seen = new Set<number>();
  const sx = Math.floor(start.x / TILE);
  const sy = Math.floor(start.y / TILE);
  const stack = [[sx, sy]];
  const key = (x: number, y: number) => y * 1000 + x;
  while (stack.length) {
    const [x, y] = stack.pop()!;
    if (x < 0 || y < 0 || x >= map.cols || y >= map.rows) continue;
    const k = key(x, y);
    if (seen.has(k)) continue;
    if (isTileSolid(map, x, y, state)) continue;
    seen.add(k);
    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }
  return seen;
}
const has = (set: Set<number>, x: number, y: number) => set.has(y * 1000 + x);

const state = newGame();
state.flags.bridgeRepaired = true; // test full connectivity
const maps = getMaps();

function inboundSpawn(id: string): Vec2 {
  for (const mid of Object.keys(maps) as (keyof typeof maps)[])
    for (const p of maps[mid].portals)
      if (p.to === id) return { x: p.spawn.x * TILE + TILE / 2, y: p.spawn.y * TILE + TILE / 2 };
  return state.player;
}

console.log("Checking spawn tiles are walkable (in the destination map)...");
for (const id of Object.keys(maps) as (keyof typeof maps)[]) {
  const map = maps[id];
  for (const p of map.portals) {
    const dest = getMap(p.to);
    if (isTileSolid(dest, p.spawn.x, p.spawn.y, state))
      fail(`${id}->${p.to}: spawns on a solid tile (${p.spawn.x},${p.spawn.y})`);
  }
}
ok("spawn tiles checked");

console.log("Checking start position is walkable...");
if (isTileSolid(getMap("village"), Math.floor(state.player.x / TILE), Math.floor(state.player.y / TILE), state))
  fail("player start is solid");
else ok("player start walkable");

console.log("Checking portals reachable from spawn / start...");
for (const id of Object.keys(maps) as (keyof typeof maps)[]) {
  const map = maps[id];
  // Reachability from the first inbound spawn (or player start for village).
  const start = id === "village" ? state.player : inboundSpawn(id);
  const reach = flood(map, state, start);
  for (const p of map.portals) {
    // portal is reachable if any of its tiles is adjacent to a walkable tile
    let reachable = false;
    for (let yy = p.y; yy < p.y + p.h; yy++)
      for (let xx = p.x; xx < p.x + p.w; xx++) if (has(reach, xx, yy)) reachable = true;
    if (!reachable) fail(`${id}: portal to ${p.to} not reachable from spawn`);
  }
  // Gatherables reachable
  for (const o of map.objects) {
    if (!o.gives && o.kind !== "well" && o.kind !== "shrine" && o.kind !== "sign") continue;
    const tx = Math.floor(o.x / TILE);
    const ty = Math.floor(o.y / TILE);
    let adj = has(reach, tx, ty) || has(reach, tx + 1, ty) || has(reach, tx - 1, ty) || has(reach, tx, ty + 1) || has(reach, tx, ty - 1);
    if (!adj) fail(`${id}: object ${o.id} (${tx},${ty}) not reachable`);
  }
}
ok("reachability checked");

console.log("Checking NPC slots are not inside solid tiles...");
for (const npc of NPC_LIST) {
  for (const phase of ["dawn", "day", "dusk", "night"] as const) {
    const slot = npc.schedule[phase];
    if (!slot) continue;
    const m = getMap(slot.map);
    if (isTileSolid(m, slot.tx, slot.ty, state))
      fail(`${npc.id} @${phase} stands on solid tile (${slot.map} ${slot.tx},${slot.ty})`);
  }
}
ok("NPC slots checked");

console.log("Checking resource economy covers quest needs...");
function countGives(item: string): number {
  let n = 0;
  for (const id of Object.keys(maps) as (keyof typeof maps)[])
    for (const o of maps[id].objects) if (o.gives === item) n++;
  return n;
}
const need: Record<string, number> = { herb: 4, wood: 3, string: 3, crystal: 1 };
for (const [item, n] of Object.entries(need)) {
  const have = countGives(item);
  if (have < n) fail(`not enough ${item}: have ${have}, need ${n}`);
  else ok(`${item}: ${have} available (need ${n})`);
}

console.log("\nClick-to-clearing requires bridge: verifying bridge blocks when broken...");
const broken = newGame();
const forest = getMap("forest");
if (!isTileSolid(forest, 24, 11, broken)) fail("broken bridge tile should be solid");
else ok("broken bridge blocks crossing");
if (isTileSolid(forest, 24, 11, state)) fail("repaired bridge tile should be passable");
else ok("repaired bridge is passable");

console.log(failures === 0 ? "\nALL CHECKS PASSED ✓" : `\n${failures} CHECK(S) FAILED ✗`);
process.exit(failures === 0 ? 0 : 1);
