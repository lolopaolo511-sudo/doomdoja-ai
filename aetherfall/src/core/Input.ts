import type { Vec2 } from "./types";

/**
 * Centralised keyboard + pointer input. The game loop reads state each frame
 * and calls `endFrame()` to clear one-shot events.
 */
export class Input {
  private down = new Set<string>();
  private pressed = new Set<string>();
  private clicks: Vec2[] = [];
  /** Latest pointer position in canvas pixels. */
  pointer: Vec2 = { x: 0, y: 0 };
  /** True while the canvas is enabled (no modal open). */
  enabled = true;

  constructor(private canvas: HTMLCanvasElement) {
    window.addEventListener("keydown", this.onKeyDown);
    window.addEventListener("keyup", this.onKeyUp);
    canvas.addEventListener("pointerdown", this.onPointerDown);
    canvas.addEventListener("pointermove", this.onPointerMove);
    window.addEventListener("blur", () => this.down.clear());
  }

  private onKeyDown = (e: KeyboardEvent) => {
    // Don't swallow typing in inputs (none here, but be safe).
    const code = e.code;
    if (MOVEMENT.has(code) || ACTION.has(code)) e.preventDefault();
    if (!this.down.has(code)) this.pressed.add(code);
    this.down.add(code);
  };

  private onKeyUp = (e: KeyboardEvent) => {
    this.down.delete(e.code);
  };

  private toCanvas(e: PointerEvent): Vec2 {
    const r = this.canvas.getBoundingClientRect();
    return {
      x: ((e.clientX - r.left) / r.width) * this.canvas.width,
      y: ((e.clientY - r.top) / r.height) * this.canvas.height,
    };
  }

  private onPointerDown = (e: PointerEvent) => {
    if (!this.enabled) return;
    this.clicks.push(this.toCanvas(e));
  };

  private onPointerMove = (e: PointerEvent) => {
    this.pointer = this.toCanvas(e);
  };

  /** Normalised movement vector from WASD / arrow keys. */
  moveAxis(): Vec2 {
    if (!this.enabled) return { x: 0, y: 0 };
    let x = 0;
    let y = 0;
    if (this.down.has("KeyA") || this.down.has("ArrowLeft")) x -= 1;
    if (this.down.has("KeyD") || this.down.has("ArrowRight")) x += 1;
    if (this.down.has("KeyW") || this.down.has("ArrowUp")) y -= 1;
    if (this.down.has("KeyS") || this.down.has("ArrowDown")) y += 1;
    if (x !== 0 && y !== 0) {
      const inv = 1 / Math.sqrt(2);
      x *= inv;
      y *= inv;
    }
    return { x, y };
  }

  isMoving(): boolean {
    const a = this.moveAxis();
    return a.x !== 0 || a.y !== 0;
  }

  justPressed(code: string): boolean {
    return this.pressed.has(code);
  }

  consumeClicks(): Vec2[] {
    const c = this.clicks;
    this.clicks = [];
    return c;
  }

  endFrame(): void {
    this.pressed.clear();
  }
}

const MOVEMENT = new Set([
  "KeyW",
  "KeyA",
  "KeyS",
  "KeyD",
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
]);
const ACTION = new Set(["Space", "KeyE", "KeyI", "KeyJ", "KeyC", "KeyM", "Escape"]);
