import type { GameState, MapData, TileKind, Vec2, WorldObject } from "../core/types";
import { TILE } from "../core/constants";
import { TILE_COLOR } from "../world/tiles";
import { lightingFor, phaseOf } from "../world/DayNight";
import { Camera } from "../core/Camera";
import { Player } from "../entities/Player";
import { circle, hash2, radialGlow, roundRect } from "./sprites";

export interface RenderNPC {
  pos: Vec2;
  color: string;
  accent: string;
  name: string;
  /** "!" new quest, "?" turn-in ready, "" none. */
  marker: string;
  facingLeft: boolean;
}

export interface RenderParams {
  map: MapData;
  state: GameState;
  time: number;
  camera: Camera;
  player: Player;
  npcs: RenderNPC[];
  /** World object/NPC currently in interaction range (for highlight). */
  highlight: Vec2 | null;
  /** Click destination marker. */
  moveTarget: Vec2 | null;
}

interface Light {
  x: number;
  y: number;
  r: number;
  color: string;
}

export class Renderer {
  ctx: CanvasRenderingContext2D;
  /** World-pixel -> screen-pixel scale. */
  zoom = 2;
  constructor(public canvas: HTMLCanvasElement) {
    const c = canvas.getContext("2d");
    if (!c) throw new Error("2D canvas unavailable");
    this.ctx = c;
    this.ctx.imageSmoothingEnabled = false;
  }

  render(p: RenderParams) {
    const { ctx } = this;
    const { camera, map, state, time } = p;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const vw = w / this.zoom;
    const vh = h / this.zoom;

    ctx.save();
    // Background fill (visible only past map edges).
    ctx.fillStyle = map.ambient;
    ctx.fillRect(0, 0, w, h);

    ctx.scale(this.zoom, this.zoom);
    ctx.translate(-Math.round(camera.x), -Math.round(camera.y));

    const phase = phaseOf(state.clock);
    const dark = phase === "night" || phase === "dusk";

    // Visible tile bounds.
    const minTX = Math.max(0, Math.floor(camera.x / TILE));
    const minTY = Math.max(0, Math.floor(camera.y / TILE));
    const maxTX = Math.min(map.cols - 1, Math.floor((camera.x + vw) / TILE));
    const maxTY = Math.min(map.rows - 1, Math.floor((camera.y + vh) / TILE));

    // --- Ground & non-tall tiles ---
    for (let ty = minTY; ty <= maxTY; ty++)
      for (let tx = minTX; tx <= maxTX; tx++) {
        const kind = map.tiles[ty][tx];
        if (kind === "tree" || kind === "bush" || kind === "rock") continue;
        this.drawTile(kind, tx, ty, time, state);
      }

    // --- Depth-sorted entities: world objects, tall tiles, NPCs, player ---
    interface Drawable {
      y: number;
      draw: () => void;
    }
    const drawables: Drawable[] = [];
    const lights: Light[] = [];

    // World objects.
    for (const obj of map.objects) {
      if (obj.gives && state.collected[obj.id]) continue;
      drawables.push({
        y: obj.y,
        draw: () => this.drawObject(obj, time, state),
      });
      const l = this.objectLight(obj, phase, state);
      if (l) lights.push(l);
    }

    // Tall tiles (trees / bushes / rocks) drawn as objects for depth feel.
    for (let ty = minTY; ty <= maxTY; ty++)
      for (let tx = minTX; tx <= maxTX; tx++) {
        const kind = map.tiles[ty][tx];
        if (kind !== "tree" && kind !== "bush" && kind !== "rock") continue;
        // Draw the ground beneath first.
        this.drawTile("grass2", tx, ty, time, state);
        const px = tx * TILE;
        const py = ty * TILE;
        drawables.push({
          y: py + TILE - 2,
          draw: () => this.drawTall(kind, px, py, tx, ty),
        });
      }

    // NPCs.
    for (const npc of p.npcs) {
      drawables.push({ y: npc.pos.y, draw: () => this.drawNPC(npc, time) });
    }

    // Player.
    drawables.push({
      y: p.player.pos.y,
      draw: () => this.drawPlayer(p.player, time),
    });

    // Highlight ring under the focused interactable.
    if (p.highlight) {
      ctx.save();
      ctx.strokeStyle = "rgba(232,200,122,0.9)";
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.lineDashOffset = -time * 12;
      circle(ctx, p.highlight.x, p.highlight.y, 20);
      ctx.stroke();
      ctx.restore();
    }

    // Move-target marker.
    if (p.moveTarget) {
      const a = 0.5 + 0.5 * Math.sin(time * 8);
      ctx.save();
      ctx.strokeStyle = `rgba(138,216,255,${a})`;
      ctx.lineWidth = 2;
      circle(ctx, p.moveTarget.x, p.moveTarget.y, 6);
      ctx.stroke();
      ctx.restore();
    }

    drawables.sort((a, b) => a.y - b.y);
    for (const d of drawables) d.draw();

    // Player lantern light at night.
    if (dark && (state.inventory.lantern ?? 0) > 0) {
      lights.push({
        x: p.player.pos.x,
        y: p.player.pos.y,
        r: 150,
        color: "rgba(255,220,150,0.55)",
      });
    }

    ctx.restore(); // end world transform

    // --- Lighting overlay ---
    this.drawLighting(p, lights);
  }

  // ----------------------------------------------------------------- tiles
  private drawTile(
    kind: TileKind,
    tx: number,
    ty: number,
    time: number,
    state: GameState,
  ) {
    const { ctx } = this;
    const px = tx * TILE;
    const py = ty * TILE;
    const n = hash2(tx, ty);

    switch (kind) {
      case "grass":
      case "grass2":
      case "flower": {
        ctx.fillStyle = kind === "grass" ? TILE_COLOR.grass : TILE_COLOR.grass2;
        ctx.fillRect(px, py, TILE, TILE);
        // grass blades
        ctx.strokeStyle = "rgba(255,255,255,0.05)";
        ctx.lineWidth = 1;
        for (let i = 0; i < 3; i++) {
          const bx = px + 4 + ((n * 97 * (i + 1)) % 24);
          const by = py + 8 + ((n * 53 * (i + 2)) % 20);
          ctx.beginPath();
          ctx.moveTo(bx, by);
          ctx.lineTo(bx, by - 5);
          ctx.stroke();
        }
        if (kind === "flower") {
          const colors = ["#e8e08a", "#e88ab0", "#9a8ae8", "#ffffff"];
          ctx.fillStyle = colors[Math.floor(n * colors.length)];
          for (let i = 0; i < 4; i++) {
            const a = (i / 4) * Math.PI * 2;
            circle(ctx, px + 16 + Math.cos(a) * 3, py + 18 + Math.sin(a) * 3, 2);
            ctx.fill();
          }
          ctx.fillStyle = "#ffd86b";
          circle(ctx, px + 16, py + 18, 2);
          ctx.fill();
        }
        break;
      }
      case "path":
      case "sand": {
        ctx.fillStyle = kind === "path" ? TILE_COLOR.path : TILE_COLOR.sand;
        ctx.fillRect(px, py, TILE, TILE);
        ctx.fillStyle = "rgba(0,0,0,0.06)";
        for (let i = 0; i < 4; i++) {
          const sx = px + ((hash2(tx + i, ty) * TILE) | 0);
          const sy = py + ((hash2(tx, ty + i) * TILE) | 0);
          circle(ctx, sx, sy, 1.5);
          ctx.fill();
        }
        break;
      }
      case "water": {
        ctx.fillStyle = TILE_COLOR.water;
        ctx.fillRect(px, py, TILE, TILE);
        ctx.strokeStyle = "rgba(255,255,255,0.18)";
        ctx.lineWidth = 1.5;
        const off = Math.sin(time * 1.5 + tx * 0.6 + ty * 0.4) * 3;
        ctx.beginPath();
        ctx.moveTo(px + 4, py + 12 + off);
        ctx.quadraticCurveTo(px + 16, py + 8 + off, px + 28, py + 12 + off);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(px + 4, py + 22 - off);
        ctx.quadraticCurveTo(px + 16, py + 18 - off, px + 28, py + 22 - off);
        ctx.stroke();
        break;
      }
      case "bridge": {
        const repaired = !!state.flags.bridgeRepaired;
        // water underneath
        ctx.fillStyle = TILE_COLOR.water;
        ctx.fillRect(px, py, TILE, TILE);
        if (repaired) {
          ctx.fillStyle = TILE_COLOR.bridge;
          ctx.fillRect(px, py, TILE, TILE);
          ctx.strokeStyle = "rgba(0,0,0,0.25)";
          for (let i = 4; i < TILE; i += 7) {
            ctx.beginPath();
            ctx.moveTo(px, py + i);
            ctx.lineTo(px + TILE, py + i);
            ctx.stroke();
          }
        } else {
          // broken plank stubs
          ctx.fillStyle = "#7a5e3a";
          ctx.fillRect(px, py, TILE, 6);
          ctx.fillRect(px, py + TILE - 6, TILE, 6);
        }
        break;
      }
      case "floor": {
        ctx.fillStyle = TILE_COLOR.floor;
        ctx.fillRect(px, py, TILE, TILE);
        ctx.strokeStyle = "rgba(0,0,0,0.12)";
        ctx.lineWidth = 1;
        for (let i = 0; i <= TILE; i += 8) {
          ctx.beginPath();
          ctx.moveTo(px, py + i);
          ctx.lineTo(px + TILE, py + i);
          ctx.stroke();
        }
        break;
      }
      case "wall": {
        ctx.fillStyle = TILE_COLOR.wall;
        ctx.fillRect(px, py, TILE, TILE);
        ctx.fillStyle = "rgba(0,0,0,0.18)";
        const row = ty % 2 === 0 ? 0 : 8;
        for (let by = 0; by < TILE; by += 8)
          for (let bx = (by / 8) % 2 ? 0 : -8; bx < TILE; bx += 16) {
            ctx.fillRect(px + bx + row, py + by + 1, 14, 6);
          }
        break;
      }
      case "ruinFloor": {
        ctx.fillStyle = TILE_COLOR.ruinFloor;
        ctx.fillRect(px, py, TILE, TILE);
        ctx.strokeStyle = "rgba(0,0,0,0.15)";
        ctx.strokeRect(px + 2, py + 2, TILE - 4, TILE - 4);
        if (n > 0.6) {
          ctx.strokeStyle = "rgba(0,0,0,0.2)";
          ctx.beginPath();
          ctx.moveTo(px + n * TILE, py);
          ctx.lineTo(px + TILE - n * TILE, py + TILE);
          ctx.stroke();
        }
        break;
      }
      case "ruinWall": {
        ctx.fillStyle = TILE_COLOR.ruinWall;
        ctx.fillRect(px, py, TILE, TILE);
        ctx.fillStyle = "rgba(255,255,255,0.06)";
        ctx.fillRect(px + 2, py + 2, TILE - 4, 4);
        ctx.fillStyle = "rgba(0,0,0,0.25)";
        ctx.fillRect(px, py + TILE - 5, TILE, 5);
        break;
      }
      case "mist": {
        ctx.fillStyle = TILE_COLOR.grass;
        ctx.fillRect(px, py, TILE, TILE);
        const a = 0.18 + 0.08 * Math.sin(time * 0.8 + tx + ty);
        ctx.fillStyle = `rgba(200,210,225,${a})`;
        ctx.fillRect(px, py, TILE, TILE);
        break;
      }
      default: {
        ctx.fillStyle = TILE_COLOR[kind] ?? "#444";
        ctx.fillRect(px, py, TILE, TILE);
      }
    }
  }

  private drawTall(kind: TileKind, px: number, py: number, tx: number, ty: number) {
    const { ctx } = this;
    const n = hash2(tx, ty);
    const cx = px + TILE / 2;
    // soft shadow
    ctx.fillStyle = "rgba(0,0,0,0.18)";
    ctx.beginPath();
    ctx.ellipse(cx, py + TILE - 3, 11, 4, 0, 0, Math.PI * 2);
    ctx.fill();

    if (kind === "tree") {
      ctx.fillStyle = "#5a3d28";
      ctx.fillRect(cx - 3, py + TILE - 14, 6, 12);
      const r = 12 + n * 3;
      ctx.fillStyle = "#1f4a2c";
      circle(ctx, cx, py + 12, r);
      ctx.fill();
      ctx.fillStyle = "#2c5e39";
      circle(ctx, cx - 4, py + 10, r * 0.7);
      ctx.fill();
      circle(ctx, cx + 5, py + 13, r * 0.6);
      ctx.fill();
      ctx.fillStyle = "rgba(150,210,140,0.25)";
      circle(ctx, cx - 5, py + 7, r * 0.35);
      ctx.fill();
    } else if (kind === "bush") {
      ctx.fillStyle = "#2c5e39";
      circle(ctx, cx - 5, py + TILE - 10, 8);
      ctx.fill();
      circle(ctx, cx + 5, py + TILE - 10, 8);
      ctx.fill();
      circle(ctx, cx, py + TILE - 14, 9);
      ctx.fill();
      if (n > 0.5) {
        ctx.fillStyle = "#c33";
        circle(ctx, cx + 3, py + TILE - 13, 2);
        ctx.fill();
      }
    } else if (kind === "rock") {
      ctx.fillStyle = "#6b6f7a";
      ctx.beginPath();
      ctx.moveTo(px + 6, py + TILE - 4);
      ctx.lineTo(px + 9, py + 12);
      ctx.lineTo(px + 18, py + 8);
      ctx.lineTo(px + 26, py + 14);
      ctx.lineTo(px + 26, py + TILE - 4);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,0.12)";
      ctx.beginPath();
      ctx.moveTo(px + 9, py + 12);
      ctx.lineTo(px + 18, py + 8);
      ctx.lineTo(px + 16, py + 16);
      ctx.closePath();
      ctx.fill();
    }
  }

  // --------------------------------------------------------------- objects
  private drawObject(obj: WorldObject, time: number, state: GameState) {
    const { ctx } = this;
    const x = obj.x;
    const y = obj.y;
    const phase = phaseOf(state.clock);
    const dark = phase === "night" || phase === "dusk";

    // shadow
    ctx.fillStyle = "rgba(0,0,0,0.16)";
    ctx.beginPath();
    ctx.ellipse(x, y + 8, 10, 3.5, 0, 0, Math.PI * 2);
    ctx.fill();

    switch (obj.kind) {
      case "sign": {
        ctx.fillStyle = "#6b4a2a";
        ctx.fillRect(x - 2, y - 4, 4, 14);
        ctx.fillStyle = "#a9743f";
        roundRect(ctx, x - 11, y - 16, 22, 13, 3);
        ctx.fill();
        ctx.fillStyle = "rgba(0,0,0,0.3)";
        for (let i = 0; i < 3; i++) ctx.fillRect(x - 7, y - 13 + i * 4, 14, 1.5);
        break;
      }
      case "well": {
        ctx.fillStyle = "#5d5b58";
        circle(ctx, x, y, 13);
        ctx.fill();
        ctx.fillStyle = "#22384a";
        circle(ctx, x, y, 9);
        ctx.fill();
        ctx.fillStyle = "#7c6b56";
        ctx.fillRect(x - 13, y - 24, 3, 22);
        ctx.fillRect(x + 10, y - 24, 3, 22);
        ctx.fillStyle = "#5a3d28";
        ctx.fillRect(x - 15, y - 27, 30, 5);
        break;
      }
      case "chest": {
        // a small heartwood woodpile
        ctx.fillStyle = "#8a5a32";
        roundRect(ctx, x - 10, y - 2, 20, 8, 2);
        ctx.fill();
        ctx.fillStyle = "#caa06a";
        circle(ctx, x - 8, y + 2, 3);
        ctx.fill();
        circle(ctx, x + 8, y + 2, 3);
        ctx.fill();
        ctx.fillStyle = "#e0c190";
        circle(ctx, x - 8, y + 2, 1.2);
        ctx.fill();
        circle(ctx, x + 8, y + 2, 1.2);
        ctx.fill();
        break;
      }
      case "campfire": {
        ctx.fillStyle = "#5a3d28";
        ctx.fillRect(x - 9, y + 2, 18, 4);
        ctx.fillRect(x - 7, y + 5, 14, 3);
        if (dark) {
          const f = 0.7 + 0.3 * Math.sin(time * 9);
          ctx.fillStyle = `rgba(255,150,40,${0.9})`;
          ctx.beginPath();
          ctx.moveTo(x - 6, y + 2);
          ctx.quadraticCurveTo(x, y - 16 * f, x + 6, y + 2);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = "rgba(255,230,120,0.95)";
          ctx.beginPath();
          ctx.moveTo(x - 3, y + 2);
          ctx.quadraticCurveTo(x, y - 9 * f, x + 3, y + 2);
          ctx.closePath();
          ctx.fill();
        } else {
          ctx.fillStyle = "#333";
          circle(ctx, x, y, 3);
          ctx.fill();
        }
        break;
      }
      case "lantern": {
        ctx.fillStyle = "#3a2c1a";
        ctx.fillRect(x - 2, y - 4, 4, 12);
        ctx.fillStyle = dark ? "#ffd86b" : "#8a7a4a";
        roundRect(ctx, x - 5, y - 16, 10, 13, 3);
        ctx.fill();
        if (dark) {
          ctx.fillStyle = "rgba(255,240,180,0.95)";
          circle(ctx, x, y - 9, 3);
          ctx.fill();
        }
        ctx.fillStyle = "#3a2c1a";
        ctx.fillRect(x - 6, y - 18, 12, 2);
        break;
      }
      case "shrine": {
        const placed = !!state.flags.charmPlaced;
        ctx.fillStyle = "#5d5b58";
        roundRect(ctx, x - 12, y - 2, 24, 10, 3);
        ctx.fill();
        ctx.fillStyle = "#6f6d68";
        roundRect(ctx, x - 9, y - 16, 18, 16, 3);
        ctx.fill();
        ctx.fillStyle = placed ? "#b59bff" : "rgba(0,0,0,0.35)";
        circle(ctx, x, y - 8, 4);
        ctx.fill();
        if (placed) {
          const a = 0.5 + 0.5 * Math.sin(time * 3);
          ctx.fillStyle = `rgba(181,155,255,${0.4 * a})`;
          circle(ctx, x, y - 8, 9);
          ctx.fill();
        }
        break;
      }
      case "herb": {
        // Moonpetal: only glows after dark (story-accurate).
        ctx.strokeStyle = dark ? "#bfe8d0" : "#3c6b48";
        ctx.lineWidth = 2;
        for (let i = -1; i <= 1; i++) {
          ctx.beginPath();
          ctx.moveTo(x, y + 6);
          ctx.quadraticCurveTo(x + i * 6, y, x + i * 7, y - 8);
          ctx.stroke();
        }
        ctx.fillStyle = dark ? "#dfffe9" : "#9fc4a8";
        for (let i = -1; i <= 1; i++) {
          circle(ctx, x + i * 7, y - 9, 2.5);
          ctx.fill();
        }
        break;
      }
      case "mushroom": {
        // Glimcap / silk node, faint glow.
        ctx.fillStyle = "#d6d0c0";
        ctx.fillRect(x - 1.5, y - 2, 3, 8);
        ctx.fillStyle = obj.gives === "string" ? "#dfe2f0" : "#e08bb0";
        ctx.beginPath();
        ctx.ellipse(x, y - 3, 7, 5, 0, Math.PI, 0);
        ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        circle(ctx, x - 2, y - 4, 1.2);
        ctx.fill();
        break;
      }
      case "crystal": {
        const glint = obj.gives === "locket";
        ctx.fillStyle = glint ? "#d8d8e0" : "#8ad8ff";
        ctx.beginPath();
        ctx.moveTo(x, y - 12);
        ctx.lineTo(x + 6, y - 2);
        ctx.lineTo(x, y + 6);
        ctx.lineTo(x - 6, y - 2);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = "rgba(255,255,255,0.55)";
        ctx.beginPath();
        ctx.moveTo(x, y - 12);
        ctx.lineTo(x + 6, y - 2);
        ctx.lineTo(x, y - 2);
        ctx.closePath();
        ctx.fill();
        break;
      }
    }
  }

  private objectLight(
    obj: WorldObject,
    phase: string,
    state: GameState,
  ): Light | null {
    if (obj.gives && state.collected[obj.id]) return null;
    const dark = phase === "night" || phase === "dusk";
    if (!dark) {
      // herbs/crystals glow faintly even by dusk only; nothing by day
      if (obj.kind === "herb") return null;
    }
    switch (obj.kind) {
      case "campfire":
        return dark ? { x: obj.x, y: obj.y, r: 110, color: "rgba(255,170,70,0.6)" } : null;
      case "lantern":
        return dark ? { x: obj.x, y: obj.y - 8, r: 80, color: "rgba(255,220,150,0.55)" } : null;
      case "herb":
        return dark ? { x: obj.x, y: obj.y - 6, r: 34, color: "rgba(180,255,200,0.5)" } : null;
      case "crystal":
        return obj.gives === "locket"
          ? null
          : { x: obj.x, y: obj.y - 4, r: 34, color: "rgba(138,216,255,0.4)" };
      case "mushroom":
        return dark ? { x: obj.x, y: obj.y - 3, r: 28, color: "rgba(230,140,180,0.4)" } : null;
      case "shrine":
        return state.flags.charmPlaced
          ? { x: obj.x, y: obj.y - 8, r: 50, color: "rgba(181,155,255,0.5)" }
          : null;
      default:
        return null;
    }
  }

  // ----------------------------------------------------------------- actors
  private drawNPC(npc: RenderNPC, time: number) {
    const { ctx } = this;
    const { x, y } = npc.pos;
    const bob = Math.sin(time * 2 + x) * 0.6;

    ctx.fillStyle = "rgba(0,0,0,0.2)";
    ctx.beginPath();
    ctx.ellipse(x, y + 9, 8, 3, 0, 0, Math.PI * 2);
    ctx.fill();

    // robe
    ctx.fillStyle = npc.color;
    roundRect(ctx, x - 7, y - 6 + bob, 14, 16, 5);
    ctx.fill();
    // collar / accent
    ctx.fillStyle = npc.accent;
    roundRect(ctx, x - 5, y - 4 + bob, 10, 5, 2);
    ctx.fill();
    // head
    ctx.fillStyle = "#e8c9a0";
    circle(ctx, x + (npc.facingLeft ? -1 : 1), y - 11 + bob, 6);
    ctx.fill();
    // hair
    ctx.fillStyle = npc.color;
    ctx.beginPath();
    ctx.arc(x + (npc.facingLeft ? -1 : 1), y - 12 + bob, 6, Math.PI, 0);
    ctx.fill();
    // eyes
    ctx.fillStyle = "#2a2230";
    const ex = npc.facingLeft ? -3 : 1;
    circle(ctx, x + ex, y - 11 + bob, 1);
    ctx.fill();
    circle(ctx, x + ex + 3, y - 11 + bob, 1);
    ctx.fill();

    // name plate
    ctx.font = "10px Spectral, serif";
    ctx.textAlign = "center";
    const tw = ctx.measureText(npc.name).width;
    ctx.fillStyle = "rgba(13,15,26,0.6)";
    roundRect(ctx, x - tw / 2 - 4, y - 30, tw + 8, 13, 4);
    ctx.fill();
    ctx.fillStyle = "#e6e8f2";
    ctx.fillText(npc.name, x, y - 20);

    // quest marker
    if (npc.marker) {
      const my = y - 36 + Math.sin(time * 4) * 2;
      ctx.font = "bold 16px Cinzel, serif";
      ctx.fillStyle = npc.marker === "!" ? "#e8c87a" : "#8ad8ff";
      ctx.fillText(npc.marker, x, my);
    }
    ctx.textAlign = "left";
  }

  private drawPlayer(player: Player, time: number) {
    const { ctx } = this;
    const { x, y } = player.pos;
    const f = player.facing;
    const step = player.moving ? Math.sin(player.animTime * 12) : 0;
    const bob = player.moving ? Math.abs(step) * 1.5 : 0;

    ctx.fillStyle = "rgba(0,0,0,0.25)";
    ctx.beginPath();
    ctx.ellipse(x, y + 9, 8, 3, 0, 0, Math.PI * 2);
    ctx.fill();

    // legs
    ctx.fillStyle = "#3a3550";
    ctx.fillRect(x - 5, y + 2, 4, 7 + step * 2);
    ctx.fillRect(x + 1, y + 2, 4, 7 - step * 2);

    // cloak / tunic
    ctx.fillStyle = "#4a7ab0";
    roundRect(ctx, x - 7, y - 7 - bob, 14, 14, 5);
    ctx.fill();
    ctx.fillStyle = "#2f5688";
    roundRect(ctx, x - 7, y - 1 - bob, 14, 8, 4);
    ctx.fill();
    // belt
    ctx.fillStyle = "#caa06a";
    ctx.fillRect(x - 7, y - 1 - bob, 14, 2);

    // head
    ctx.fillStyle = "#f0d0a8";
    circle(ctx, x, y - 12 - bob, 6);
    ctx.fill();
    // hair / hood
    ctx.fillStyle = "#6a4a8a";
    ctx.beginPath();
    ctx.arc(x, y - 13 - bob, 6, Math.PI, 0);
    ctx.fill();

    // face by facing
    ctx.fillStyle = "#2a2230";
    if (f !== "up") {
      const dx = f === "left" ? -2 : f === "right" ? 2 : 0;
      circle(ctx, x - 2 + dx, y - 12 - bob, 1.1);
      ctx.fill();
      circle(ctx, x + 2 + dx, y - 12 - bob, 1.1);
      ctx.fill();
    }
    void time;
  }

  // --------------------------------------------------------------- lighting
  private drawLighting(p: RenderParams, lights: Light[]) {
    const { ctx } = this;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const { darkness, tint } = lightingFor(p.state.clock);
    if (darkness <= 0.001) return;

    // Build the darkness layer on an offscreen buffer so we can punch lights.
    ctx.save();
    ctx.globalCompositeOperation = "multiply";
    ctx.fillStyle = applyAlpha(tint, darkness);
    ctx.fillRect(0, 0, w, h);
    ctx.restore();

    // Add warm light pools (screen blend so they brighten).
    ctx.save();
    ctx.globalCompositeOperation = "screen";
    for (const l of lights) {
      const sx = (l.x - p.camera.x) * this.zoom;
      const sy = (l.y - p.camera.y) * this.zoom;
      if (sx < -300 || sy < -300 || sx > w + 300 || sy > h + 300) continue;
      radialGlow(ctx, sx, sy, l.r * this.zoom, scaleAlpha(l.color, darkness));
    }
    ctx.restore();
  }
}

// Convert "#rrggbb" + alpha to rgba string.
function applyAlpha(hex: string, a: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  // Lighter base so multiply darkens toward the tint, not to black.
  const mix = (c: number) => Math.round(c + (255 - c) * (1 - a));
  return `rgba(${mix(r)},${mix(g)},${mix(b)},1)`;
}

function scaleAlpha(rgba: string, k: number): string {
  const m = rgba.match(/rgba?\(([^)]+)\)/);
  if (!m) return rgba;
  const parts = m[1].split(",").map((s) => s.trim());
  const a = parts.length === 4 ? parseFloat(parts[3]) : 1;
  return `rgba(${parts[0]},${parts[1]},${parts[2]},${(a * k).toFixed(3)})`;
}
