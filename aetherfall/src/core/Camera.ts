import type { Vec2 } from "./types";

/** A camera that smoothly follows a target and clamps to the map bounds. */
export class Camera {
  x = 0;
  y = 0;

  constructor(
    public viewW: number,
    public viewH: number,
  ) {}

  /** Snap instantly (used on map change). */
  snapTo(target: Vec2, worldW: number, worldH: number) {
    this.x = this.clampX(target.x - this.viewW / 2, worldW);
    this.y = this.clampY(target.y - this.viewH / 2, worldH);
  }

  follow(target: Vec2, worldW: number, worldH: number, dt: number) {
    const tx = this.clampX(target.x - this.viewW / 2, worldW);
    const ty = this.clampY(target.y - this.viewH / 2, worldH);
    // Critically-damped-ish smoothing.
    const k = 1 - Math.pow(0.0008, dt);
    this.x += (tx - this.x) * k;
    this.y += (ty - this.y) * k;
  }

  private clampX(x: number, worldW: number) {
    if (worldW <= this.viewW) return (worldW - this.viewW) / 2;
    return Math.max(0, Math.min(x, worldW - this.viewW));
  }
  private clampY(y: number, worldH: number) {
    if (worldH <= this.viewH) return (worldH - this.viewH) / 2;
    return Math.max(0, Math.min(y, worldH - this.viewH));
  }

  screenToWorld(p: Vec2): Vec2 {
    return { x: p.x + this.x, y: p.y + this.y };
  }
  worldToScreen(p: Vec2): Vec2 {
    return { x: p.x - this.x, y: p.y - this.y };
  }
}
