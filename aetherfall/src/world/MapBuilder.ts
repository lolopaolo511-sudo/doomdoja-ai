import type { TileKind } from "../core/types";

/** Tiny deterministic helper for laying out tile grids. */
export class MapBuilder {
  cols: number;
  rows: number;
  tiles: TileKind[][];
  private seed: number;

  constructor(cols: number, rows: number, fill: TileKind, seed = 1) {
    this.cols = cols;
    this.rows = rows;
    this.seed = seed;
    this.tiles = Array.from({ length: rows }, () =>
      Array.from({ length: cols }, () => fill),
    );
  }

  /** Deterministic pseudo-random in [0,1). */
  rand(): number {
    this.seed = (this.seed * 1664525 + 1013904223) % 0xffffffff;
    return this.seed / 0xffffffff;
  }

  inBounds(x: number, y: number): boolean {
    return x >= 0 && y >= 0 && x < this.cols && y < this.rows;
  }

  set(x: number, y: number, kind: TileKind): this {
    if (this.inBounds(x, y)) this.tiles[y][x] = kind;
    return this;
  }

  rect(x: number, y: number, w: number, h: number, kind: TileKind): this {
    for (let j = y; j < y + h; j++)
      for (let i = x; i < x + w; i++) this.set(i, j, kind);
    return this;
  }

  /** Hollow rectangle outline (e.g. building walls). */
  outline(x: number, y: number, w: number, h: number, kind: TileKind): this {
    for (let i = x; i < x + w; i++) {
      this.set(i, y, kind);
      this.set(i, y + h - 1, kind);
    }
    for (let j = y; j < y + h; j++) {
      this.set(x, j, kind);
      this.set(x + w - 1, j, kind);
    }
    return this;
  }

  border(kind: TileKind, thickness = 1): this {
    for (let t = 0; t < thickness; t++)
      this.outline(t, t, this.cols - t * 2, this.rows - t * 2, kind);
    return this;
  }

  hLine(x: number, y: number, len: number, kind: TileKind): this {
    for (let i = x; i < x + len; i++) this.set(i, y, kind);
    return this;
  }

  vLine(x: number, y: number, len: number, kind: TileKind): this {
    for (let j = y; j < y + len; j++) this.set(x, j, kind);
    return this;
  }

  /** Sprinkle `count` tiles of `kind` over tiles currently matching `over`. */
  scatter(kind: TileKind, count: number, over: TileKind[]): this {
    let placed = 0;
    let guard = 0;
    while (placed < count && guard < count * 40) {
      guard++;
      const x = Math.floor(this.rand() * this.cols);
      const y = Math.floor(this.rand() * this.rows);
      if (over.includes(this.tiles[y][x])) {
        this.set(x, y, kind);
        placed++;
      }
    }
    return this;
  }
}
