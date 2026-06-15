import type { MapData, MapId } from "../core/types";
import { TILE } from "../core/constants";
import { MapBuilder } from "./MapBuilder";

/** Convenience: tile coords -> pixel center of that tile. */
export function tileCenter(tx: number, ty: number) {
  return { x: tx * TILE + TILE / 2, y: ty * TILE + TILE / 2 };
}

// ---------------------------------------------------------------------------
// VILLAGE — the starting hub.
// ---------------------------------------------------------------------------
function buildVillage(): MapData {
  const b = new MapBuilder(30, 22, "grass", 7);
  b.scatter("grass2", 90, ["grass"]);
  b.border("tree", 1);

  // Central crossroads of paths.
  b.hLine(1, 11, 28, "path");
  b.vLine(14, 1, 20, "path");
  b.rect(12, 9, 6, 5, "path");

  // A pond in the north-west with a sandy shore.
  b.rect(3, 3, 5, 4, "water");
  b.outline(2, 2, 7, 6, "sand");

  // Houses (walls with floor interiors + a door gap).
  const house = (x: number, y: number, w: number, h: number, doorX: number) => {
    b.rect(x, y, w, h, "floor");
    b.outline(x, y, w, h, "wall");
    b.set(doorX, y + h - 1, "floor"); // doorway
  };
  house(4, 14, 5, 4, 6); // Mira's cottage (SW)
  house(21, 3, 6, 4, 23); // Bertram's house (NE)
  house(21, 15, 6, 5, 23); // Garrin's workshop (SE)
  house(9, 4, 5, 4, 11); // Selene's study (NW)

  // Flower beds + bushes for life.
  b.scatter("flower", 26, ["grass", "grass2"]);
  b.scatter("bush", 14, ["grass", "grass2"]);

  // East gateway out to the forest (cut through the tree border).
  b.rect(29, 10, 1, 3, "path");

  return {
    id: "village",
    name: "Wend Village",
    cols: b.cols,
    rows: b.rows,
    tiles: b.tiles,
    ambient: "#3c5a3e",
    portals: [
      {
        x: 29,
        y: 10,
        w: 1,
        h: 3,
        to: "forest",
        spawn: { x: 2, y: 11 },
        label: "Ancient Forest →",
      },
    ],
    objects: [
      { id: "well", kind: "well", ...tileCenter(14, 11), text: "The village well. Cool spring water rises from the dark." },
      { id: "village_sign", kind: "sign", ...tileCenter(15, 12), text: "WEND VILLAGE — Travellers welcome. Mind the forest after dark." },
      { id: "village_fire", kind: "campfire", ...tileCenter(13, 13) },
      { id: "village_lantern1", kind: "lantern", ...tileCenter(11, 11) },
      { id: "village_lantern2", kind: "lantern", ...tileCenter(17, 11) },
      { id: "garrin_sign", kind: "sign", ...tileCenter(20, 17), text: "GARRIN'S WORKSHOP — Carpentry, repairs, and honest work." },
    ],
  };
}

// ---------------------------------------------------------------------------
// FOREST — connects village, ruins (north) and clearing (across the bridge).
// ---------------------------------------------------------------------------
function buildForest(): MapData {
  const b = new MapBuilder(32, 24, "grass2", 31);
  b.scatter("grass", 120, ["grass2"]);
  b.border("tree", 2);

  // A river splitting the map; a bridge crosses it to the east clearing.
  b.vLine(24, 0, 24, "water");
  b.vLine(25, 0, 24, "water");
  // Broken bridge gap at rows 10-12 (rendered specially; passable only repaired).
  b.set(24, 11, "bridge");
  b.set(25, 11, "bridge");

  // Winding path from the west entrance toward the bridge and north fork.
  b.hLine(1, 11, 23, "path");
  b.vLine(12, 1, 11, "path");

  // North clearing leads to the ruins.
  b.rect(9, 1, 7, 4, "path");

  // Dense tree clusters for character.
  b.scatter("tree", 70, ["grass", "grass2"]);
  b.scatter("bush", 28, ["grass", "grass2"]);
  b.scatter("flower", 18, ["grass", "grass2"]);
  // Keep the main path clear.
  b.hLine(1, 11, 23, "path");
  b.vLine(12, 1, 11, "path");

  // Gateways: west to village, and the east bridge landing to the clearing.
  b.rect(0, 10, 1, 3, "path");
  b.rect(26, 10, 2, 3, "path");

  return {
    id: "forest",
    name: "Ancient Forest",
    cols: b.cols,
    rows: b.rows,
    tiles: b.tiles,
    ambient: "#28432e",
    portals: [
      {
        x: 0,
        y: 10,
        w: 1,
        h: 3,
        to: "village",
        spawn: { x: 28, y: 11 },
        label: "← Wend Village",
      },
      {
        x: 10,
        y: 1,
        w: 5,
        h: 1,
        to: "ruins",
        spawn: { x: 14, y: 19 },
        label: "Stone Ruins ↑",
      },
      // Bridge crossing to the clearing — only active once the bridge is mended.
      {
        x: 26,
        y: 10,
        w: 2,
        h: 3,
        to: "clearing",
        spawn: { x: 2, y: 9 },
        label: "Misty Clearing →",
      },
    ],
    objects: [
      { id: "forest_sign", kind: "sign", ...tileCenter(6, 12), text: "Paths fork ahead: north to old stones, east across the river." },
      // Gatherables
      { id: "herb1", kind: "herb", ...tileCenter(5, 8), gives: "herb", once: true },
      { id: "herb2", kind: "herb", ...tileCenter(8, 15), gives: "herb", once: true },
      { id: "herb3", kind: "herb", ...tileCenter(18, 6), gives: "herb", once: true },
      { id: "herb4", kind: "herb", ...tileCenter(20, 16), gives: "herb", once: true },
      { id: "herb5", kind: "herb", ...tileCenter(15, 18), gives: "herb", once: true },
      { id: "wood1", kind: "chest", ...tileCenter(4, 17), gives: "wood", once: true },
      { id: "wood2", kind: "chest", ...tileCenter(17, 19), gives: "wood", once: true },
      { id: "wood3", kind: "chest", ...tileCenter(9, 19), gives: "wood", once: true },
      { id: "wood4", kind: "chest", ...tileCenter(6, 13), gives: "wood", once: true },
      { id: "wood5", kind: "chest", ...tileCenter(14, 4), gives: "wood", once: true },
      { id: "mush1", kind: "mushroom", ...tileCenter(6, 5), gives: "mushroom", once: true },
      { id: "mush2", kind: "mushroom", ...tileCenter(21, 9), gives: "mushroom", once: true },
      // Hidden locket for Bertram's quest.
      { id: "locket", kind: "crystal", ...tileCenter(19, 3), gives: "locket", once: true, text: "Something silver glints among the roots…" },
      { id: "forest_shrine", kind: "lantern", ...tileCenter(12, 6) },
    ],
  };
}

// ---------------------------------------------------------------------------
// RUINS — north of the forest. Stone, shards, silk, and a shrine.
// ---------------------------------------------------------------------------
function buildRuins(): MapData {
  const b = new MapBuilder(28, 22, "ruinFloor", 53);
  // Surround with crumbling walls; cracked rock outside.
  b.scatter("rock", 60, ["ruinFloor"]);
  b.border("ruinWall", 2);

  // Roofless chambers.
  b.outline(4, 4, 8, 7, "ruinWall");
  b.outline(16, 4, 8, 7, "ruinWall");
  b.outline(9, 12, 10, 7, "ruinWall");
  // Doorways into chambers.
  b.set(7, 10, "ruinFloor");
  b.set(19, 10, "ruinFloor");
  b.set(13, 18, "ruinFloor");

  // Central processional path.
  b.vLine(14, 1, 20, "path");
  b.hLine(1, 10, 26, "path");

  // Reopen chamber interiors as floor.
  b.rect(5, 5, 6, 5, "ruinFloor");
  b.rect(17, 5, 6, 5, "ruinFloor");
  b.rect(10, 13, 8, 5, "ruinFloor");
  b.set(7, 10, "ruinFloor");
  b.set(19, 10, "ruinFloor");
  b.set(13, 18, "ruinFloor");
  b.vLine(14, 1, 9, "path");

  return {
    id: "ruins",
    name: "Stone Ruins",
    cols: b.cols,
    rows: b.rows,
    tiles: b.tiles,
    ambient: "#3a3a44",
    portals: [
      {
        x: 14,
        y: 20,
        w: 1,
        h: 1,
        to: "forest",
        spawn: { x: 12, y: 2 },
        label: "↓ Ancient Forest",
      },
    ],
    objects: [
      { id: "ruins_sign", kind: "sign", ...tileCenter(14, 9), text: "Worn glyphs: 'Where the sky fell, bind the echo, and be still.'" },
      { id: "shrine", kind: "shrine", ...tileCenter(13, 15), text: "A cracked shrine. A shard-shaped hollow sits empty at its center." },
      // Shards
      { id: "crystal1", kind: "crystal", ...tileCenter(6, 6), gives: "crystal", once: true },
      { id: "crystal2", kind: "crystal", ...tileCenter(21, 6), gives: "crystal", once: true },
      { id: "crystal3", kind: "crystal", ...tileCenter(5, 16), gives: "crystal", once: true },
      // Silk
      { id: "silk1", kind: "mushroom", ...tileCenter(20, 15), gives: "string", once: true, text: "Spider silk, strung between fallen stones." },
      { id: "silk2", kind: "mushroom", ...tileCenter(22, 16), gives: "string", once: true, text: "Spider silk, strung between fallen stones." },
      { id: "silk3", kind: "mushroom", ...tileCenter(7, 14), gives: "string", once: true, text: "Spider silk, strung between fallen stones." },
      { id: "silk4", kind: "mushroom", ...tileCenter(11, 16), gives: "string", once: true, text: "Spider silk, strung between fallen stones." },
    ],
  };
}

// ---------------------------------------------------------------------------
// CLEARING — across the bridge. Misty, quiet, home to the hermit.
// ---------------------------------------------------------------------------
function buildClearing(): MapData {
  const b = new MapBuilder(26, 20, "grass", 89);
  b.scatter("grass2", 70, ["grass"]);
  b.scatter("mist", 50, ["grass", "grass2"]);
  b.border("tree", 2);

  // A still pool in the center.
  b.rect(10, 8, 6, 5, "water");
  b.outline(9, 7, 8, 7, "sand");

  // Hermit's hut on the east side.
  b.rect(19, 5, 5, 5, "floor");
  b.outline(19, 5, 5, 5, "wall");
  b.set(19, 7, "floor"); // door facing the path

  // Path from west entrance to the hut + pool.
  b.hLine(1, 9, 18, "path");
  b.rect(7, 7, 3, 5, "path");

  b.scatter("flower", 24, ["grass", "grass2"]);
  b.scatter("bush", 12, ["grass", "grass2"]);

  // West gateway back to the forest bridge.
  b.rect(0, 8, 1, 3, "path");

  return {
    id: "clearing",
    name: "Misty Clearing",
    cols: b.cols,
    rows: b.rows,
    tiles: b.tiles,
    ambient: "#3a4a52",
    portals: [
      {
        x: 0,
        y: 8,
        w: 1,
        h: 3,
        to: "forest",
        spawn: { x: 23, y: 11 },
        label: "← Ancient Forest",
      },
    ],
    objects: [
      { id: "clearing_sign", kind: "sign", ...tileCenter(4, 10), text: "The mist drinks every sound. Tread gently." },
      { id: "clearing_shrine", kind: "shrine", ...tileCenter(13, 6), text: "A mossy standing stone, humming faintly with aether." },
      { id: "clearing_crystal", kind: "crystal", ...tileCenter(5, 15), gives: "crystal", once: true },
      { id: "clearing_herb1", kind: "herb", ...tileCenter(20, 14), gives: "herb", once: true },
      { id: "clearing_herb2", kind: "herb", ...tileCenter(22, 12), gives: "herb", once: true },
      { id: "clearing_fire", kind: "campfire", ...tileCenter(17, 12) },
    ],
  };
}

let cache: Record<MapId, MapData> | null = null;

export function getMaps(): Record<MapId, MapData> {
  if (!cache) {
    cache = {
      village: buildVillage(),
      forest: buildForest(),
      ruins: buildRuins(),
      clearing: buildClearing(),
    };
  }
  return cache;
}

export function getMap(id: MapId): MapData {
  return getMaps()[id];
}
