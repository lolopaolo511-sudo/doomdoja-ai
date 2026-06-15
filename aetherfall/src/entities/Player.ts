import type { GameState, MapData, Vec2 } from "../core/types";
import { PLAYER_H, PLAYER_SPEED, PLAYER_W, TILE } from "../core/constants";
import { boxCollides } from "../world/collision";
import { Input } from "../core/Input";

export type Facing = "down" | "up" | "left" | "right";

export class Player {
  facing: Facing = "down";
  animTime = 0;
  moving = false;
  /** Click-to-move waypoints (pixel centers). */
  private path: Vec2[] = [];

  constructor(private state: GameState) {}

  get pos(): Vec2 {
    return this.state.player;
  }

  setPath(path: Vec2[] | null) {
    this.path = path ?? [];
  }

  clearPath() {
    this.path = [];
  }

  get pathTarget(): Vec2 | null {
    return this.path.length ? this.path[this.path.length - 1] : null;
  }

  update(dt: number, input: Input, map: MapData) {
    const axis = input.moveAxis();
    let dx = 0;
    let dy = 0;

    if (axis.x !== 0 || axis.y !== 0) {
      // Manual control overrides any active path.
      this.path = [];
      dx = axis.x * PLAYER_SPEED * dt;
      dy = axis.y * PLAYER_SPEED * dt;
    } else if (this.path.length) {
      const wp = this.path[0];
      const ddx = wp.x - this.pos.x;
      const ddy = wp.y - this.pos.y;
      const dist = Math.hypot(ddx, ddy);
      if (dist < 3) {
        this.path.shift();
      } else {
        const step = PLAYER_SPEED * dt;
        const t = Math.min(1, step / dist);
        dx = ddx * t;
        dy = ddy * t;
      }
    }

    this.moving = dx !== 0 || dy !== 0;
    if (this.moving) {
      this.applyMove(dx, dy, map);
      this.updateFacing(dx, dy);
      this.animTime += dt;
    } else {
      this.animTime = 0;
    }
  }

  private applyMove(dx: number, dy: number, map: MapData) {
    const hw = PLAYER_W / 2;
    const hh = PLAYER_H / 2;
    const p = this.pos;
    // Move on each axis independently so we slide along walls.
    if (dx !== 0 && !boxCollides(map, this.state, p.x + dx, p.y, hw, hh, TILE)) {
      p.x += dx;
    } else if (dx !== 0) {
      this.path = []; // blocked: stop auto-walking into a wall
    }
    if (dy !== 0 && !boxCollides(map, this.state, p.x, p.y + dy, hw, hh, TILE)) {
      p.y += dy;
    } else if (dy !== 0) {
      this.path = [];
    }
  }

  private updateFacing(dx: number, dy: number) {
    if (Math.abs(dx) > Math.abs(dy)) {
      this.facing = dx < 0 ? "left" : "right";
    } else if (dy !== 0) {
      this.facing = dy < 0 ? "up" : "down";
    }
  }
}
