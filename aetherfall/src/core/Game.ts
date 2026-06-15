import type {
  DialogContext,
  DialogTree,
  GameState,
  MapData,
  Vec2,
  WorldObject,
} from "./types";
import {
  INTERACT_RANGE,
  MINUTES_PER_DAY,
  SECONDS_PER_MINUTE,
  TILE,
} from "./constants";
import { newGame, cloneState } from "./state";
import { Input } from "./Input";
import { Camera } from "./Camera";
import { Player } from "../entities/Player";
import { Renderer, RenderNPC } from "../render/Renderer";
import { UI, SatchelTab } from "../ui/UI";
import { getMap } from "../world/maps";
import { phaseOf } from "../world/DayNight";
import { findPath } from "../systems/pathfind";
import { SaveSystem } from "../systems/SaveSystem";
import { Inventory } from "../systems/Inventory";
import { Crafting } from "../systems/Crafting";
import { QuestSystem } from "../systems/QuestSystem";
import { ITEMS } from "../data/items";
import { QUESTS } from "../data/quests";
import { NPCS, NPC_LIST, slotPos } from "../entities/npcs";

interface Interactable {
  pos: Vec2;
  prompt: string;
  act: () => void;
}

type DialogRuntime =
  | { kind: "npc"; npcId: string; tree: DialogTree; nodeId: string }
  | { kind: "custom" }
  | null;

export class Game {
  private canvas: HTMLCanvasElement;
  private input: Input;
  private camera: Camera;
  private renderer: Renderer;
  private ui: UI;

  private state!: GameState;
  private player!: Player;
  private map!: MapData;

  private started = false;
  private last = 0;
  private time = 0;
  private saveTimer = 0;

  private dialog: DialogRuntime = null;
  private choiceActions: Array<() => void> = [];
  private focus: Interactable | null = null;

  constructor(root: HTMLElement) {
    this.ui = new UI(root, {
      hasSave: () => SaveSystem.hasSave(),
      newGame: () => this.startNew(),
      continueGame: () => this.continue(),
      pickChoice: (i) => this.pickChoice(i),
      craft: (id) => this.doCraft(id),
      save: () => this.save(true),
      resume: () => this.ui.hidePause(),
      toMenu: () => this.toMenu(),
      closePanel: () => this.ui.closeSatchel(),
    });
    this.ui.requestSatchel = (tab) => this.openSatchel(tab);
    this.ui.requestPause = () => this.togglePause();

    this.canvas = root.querySelector("#game") as HTMLCanvasElement;
    this.input = new Input(this.canvas);
    this.renderer = new Renderer(this.canvas);
    this.camera = new Camera(100, 100);

    this.resize();
    window.addEventListener("resize", () => this.resize());

    this.ui.showMenu();
    requestAnimationFrame((t) => this.loop(t));
  }

  // ---------------------------------------------------------------- lifecycle
  private resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.floor(window.innerWidth * dpr);
    this.canvas.height = Math.floor(window.innerHeight * dpr);
    // Keep tiles a comfortable size regardless of screen.
    this.renderer.zoom = Math.max(1.5, Math.min(3, (this.canvas.width / 1280) * 2));
    this.camera.viewW = this.canvas.width / this.renderer.zoom;
    this.camera.viewH = this.canvas.height / this.renderer.zoom;
    if (this.started) this.snapCamera();
  }

  private startNew() {
    this.beginWith(newGame());
  }

  private continue() {
    const s = SaveSystem.load();
    if (!s) {
      this.ui.toast("No save found — starting anew.");
      this.beginWith(newGame());
      return;
    }
    this.beginWith(s);
    this.ui.toast("Welcome back to Aetherfall.");
  }

  private beginWith(state: GameState) {
    this.state = state;
    this.player = new Player(this.state);
    this.loadMap(this.state.map, false);
    this.started = true;
    this.dialog = null;
    this.ui.hideMenu();
    this.ui.hideDialog();
    this.ui.hidePause();
    this.ui.closeSatchel();
    this.ui.setHudVisible(true);
    this.snapCamera();
    QuestSystem.refresh(this.state);
  }

  private toMenu() {
    this.save(false);
    this.started = false;
    this.ui.setHudVisible(false);
    this.ui.hidePause();
    this.ui.closeSatchel();
    this.ui.hideDialog();
    this.ui.showMenu();
  }

  private loadMap(id: GameState["map"], announce = true) {
    this.state.map = id;
    this.map = getMap(id);
    if (announce) this.ui.toast(`Entering ${this.map.name}`);
  }

  private snapCamera() {
    this.camera.snapTo(
      this.player.pos,
      this.map.cols * TILE,
      this.map.rows * TILE,
    );
  }

  // ---------------------------------------------------------------- main loop
  private loop(t: number) {
    const dt = Math.min(0.05, (t - this.last) / 1000 || 0);
    this.last = t;
    this.time += dt;

    if (this.started) {
      this.handleKeys();
      const paused = this.isPaused();
      this.input.enabled = !paused;
      if (!paused) this.simulate(dt);
      this.camera.follow(
        this.player.pos,
        this.map.cols * TILE,
        this.map.rows * TILE,
        dt,
      );
      this.draw();
    }

    this.input.endFrame();
    requestAnimationFrame((n) => this.loop(n));
  }

  private isPaused(): boolean {
    return (
      this.ui.isSatchelOpen() ||
      this.ui.isPauseOpen() ||
      this.ui.isDialogOpen()
    );
  }

  // ---------------------------------------------------------------- keys
  private handleKeys() {
    const I = this.input;
    // Dialog: number keys / space to advance handled implicitly via UI buttons.
    if (this.ui.isDialogOpen()) {
      if (I.justPressed("Escape")) this.endDialog();
      for (let i = 0; i < 9; i++) {
        if (I.justPressed(`Digit${i + 1}`)) this.pickChoice(i);
      }
      if (I.justPressed("Space") && this.choiceActions.length === 1) this.pickChoice(0);
      return;
    }

    if (I.justPressed("Escape")) {
      if (this.ui.isSatchelOpen()) this.ui.closeSatchel();
      else this.togglePause();
      return;
    }
    if (this.ui.isPauseOpen()) return;

    if (I.justPressed("KeyI")) this.toggleSatchel("inventory");
    if (I.justPressed("KeyC")) this.toggleSatchel("crafting");
    if (I.justPressed("KeyJ") || I.justPressed("KeyQ")) this.toggleSatchel("quests");

    if (!this.ui.isSatchelOpen()) {
      if (I.justPressed("KeyE") || I.justPressed("Space")) this.tryInteract();
    }
  }

  private togglePause() {
    if (this.ui.isPauseOpen()) this.ui.hidePause();
    else {
      this.ui.closeSatchel();
      this.ui.showPause();
    }
  }

  private toggleSatchel(tab: SatchelTab) {
    if (this.ui.isSatchelOpen()) this.ui.closeSatchel();
    else this.openSatchel(tab);
  }

  private openSatchel(tab: SatchelTab) {
    this.ui.hidePause();
    QuestSystem.refresh(this.state);
    this.ui.openSatchel(tab, this.state);
  }

  // ---------------------------------------------------------------- simulate
  private simulate(dt: number) {
    // Advance the world clock.
    this.state.clock += dt / SECONDS_PER_MINUTE;
    while (this.state.clock >= MINUTES_PER_DAY) {
      this.state.clock -= MINUTES_PER_DAY;
      this.state.day += 1;
    }

    // Click-to-move / click-to-interact.
    for (const click of this.input.consumeClicks()) {
      const world = {
        x: click.x / this.renderer.zoom + this.camera.x,
        y: click.y / this.renderer.zoom + this.camera.y,
      };
      this.handleClick(world);
    }

    this.player.update(dt, this.input, this.map);
    this.checkPortals();
    this.updateFocus();

    QuestSystem.refresh(this.state);

    this.saveTimer += dt;
    if (this.saveTimer > 20) {
      this.saveTimer = 0;
      this.save(false);
    }
  }

  private handleClick(world: Vec2) {
    // If an interactable is right under the cursor and we're in range, use it.
    const list = this.interactables();
    let near: Interactable | null = null;
    let best = 26;
    for (const it of list) {
      const d = Math.hypot(it.pos.x - world.x, it.pos.y - world.y);
      if (d < best) {
        best = d;
        near = it;
      }
    }
    if (near && this.dist(near.pos) <= INTERACT_RANGE) {
      near.act();
      return;
    }
    // Otherwise walk there.
    const path = findPath(this.map, this.state, this.player.pos, world);
    this.player.setPath(path);
  }

  private dist(p: Vec2): number {
    return Math.hypot(p.x - this.player.pos.x, p.y - this.player.pos.y);
  }

  private checkPortals() {
    const px = Math.floor(this.player.pos.x / TILE);
    const py = Math.floor(this.player.pos.y / TILE);
    for (const portal of this.map.portals) {
      // The bridge portal only works once the bridge is mended.
      if (portal.to === "clearing" && !this.state.flags.bridgeRepaired) continue;
      if (
        px >= portal.x &&
        px < portal.x + portal.w &&
        py >= portal.y &&
        py < portal.y + portal.h
      ) {
        this.player.clearPath();
        this.loadMap(portal.to);
        this.state.player.x = portal.spawn.x * TILE + TILE / 2;
        this.state.player.y = portal.spawn.y * TILE + TILE / 2;
        this.snapCamera();
        this.save(false);
        return;
      }
    }
  }

  // ---------------------------------------------------------------- interact
  /** Everything on the current map the player could interact with. */
  private interactables(): Interactable[] {
    const list: Interactable[] = [];
    const phase = phaseOf(this.state.clock);

    // NPCs present on this map this phase.
    for (const npc of NPC_LIST) {
      const slot = npc.schedule[phase];
      if (!slot || slot.map !== this.state.map) continue;
      const pos = slotPos(slot)!;
      list.push({
        pos,
        prompt: `talk to ${npc.name}`,
        act: () => this.startDialog(npc.id),
      });
    }

    // World objects.
    for (const obj of this.map.objects) {
      const it = this.objectInteractable(obj);
      if (it) list.push(it);
    }

    // The broken forest bridge (a virtual interactable).
    if (this.state.map === "forest" && !this.state.flags.bridgeRepaired) {
      list.push({
        pos: { x: 24 * TILE + TILE / 2, y: 11 * TILE + TILE / 2 },
        prompt: "mend the bridge",
        act: () => this.mendBridge(),
      });
    }

    return list;
  }

  private objectInteractable(obj: WorldObject): Interactable | null {
    const dark = ["night", "dusk"].includes(phaseOf(this.state.clock));
    if (obj.gives) {
      if (this.state.collected[obj.id]) return null;
      const item = ITEMS[obj.gives];
      return {
        pos: { x: obj.x, y: obj.y },
        prompt: `gather ${item?.name ?? obj.gives}`,
        act: () => {
          // Moonpetal can only be gathered after dark.
          if (obj.gives === "herb" && !dark) {
            this.message("Moonpetal Herb", "", "It's curled shut and dull in the daylight. Moonpetal only glows — and can only be gathered — after dark.");
            return;
          }
          this.state.collected[obj.id] = true;
          Inventory.add(this.state, obj.gives!, 1);
          this.ui.toast(`+1 ${ITEMS[obj.gives!].name}`);
          QuestSystem.refresh(this.state);
        },
      };
    }
    switch (obj.kind) {
      case "well":
        return {
          pos: { x: obj.x, y: obj.y },
          prompt: "draw water",
          act: () => {
            Inventory.add(this.state, "water", 1);
            this.ui.toast("+1 Vial of Springwater");
          },
        };
      case "sign":
        return {
          pos: { x: obj.x, y: obj.y },
          prompt: "read the sign",
          act: () => this.message("Sign", "", obj.text ?? "..."),
        };
      case "shrine":
        return {
          pos: { x: obj.x, y: obj.y },
          prompt: obj.id === "shrine" ? "inspect the shrine" : "inspect",
          act: () => this.inspectShrine(obj),
        };
      case "campfire":
        return {
          pos: { x: obj.x, y: obj.y },
          prompt: "rest by the fire",
          act: () => this.restAtFire(),
        };
      default:
        return null;
    }
  }

  private updateFocus() {
    const list = this.interactables();
    let best: Interactable | null = null;
    let bestD = INTERACT_RANGE;
    for (const it of list) {
      const d = this.dist(it.pos);
      if (d <= bestD) {
        bestD = d;
        best = it;
      }
    }
    this.focus = best;
    this.ui.setInteractPrompt(best ? best.prompt : null);
  }

  private tryInteract() {
    if (this.focus) this.focus.act();
  }

  private mendBridge() {
    if (Inventory.remove(this.state, "bridgeplank", 1)) {
      this.state.flags.bridgeRepaired = true;
      this.ui.toast("You lay the planks across — the bridge holds!");
      QuestSystem.refresh(this.state);
      const def = QuestSystem.complete(this.state, "bridge");
      if (def) this.announceComplete(def);
    } else {
      this.message(
        "Broken Bridge",
        "",
        "The span has fallen into the river. You'll need Bound Planks — three heartwood lashed with silk — to mend it.",
      );
    }
  }

  private inspectShrine(obj: WorldObject) {
    if (obj.id !== "shrine") {
      this.message("Standing Stone", "", obj.text ?? "An old stone, humming faintly.");
      return;
    }
    if (this.state.flags.charmPlaced) {
      this.message("The Shrine", "", "The charm rests in the hollow. The ruins are quiet now — you can almost hear the stones breathing.");
      return;
    }
    if (Inventory.remove(this.state, "charm", 1)) {
      this.state.flags.charmPlaced = true;
      this.ui.toast("The charm settles into the hollow. The whispers fade…");
      QuestSystem.refresh(this.state);
      const def = QuestSystem.complete(this.state, "ruins");
      if (def) this.announceComplete(def);
    } else {
      this.message(
        "The Shrine",
        "",
        obj.text ?? "A shard-shaped hollow sits empty. An Aether Charm might fit here.",
      );
    }
  }

  private restAtFire() {
    const hour = (this.state.clock % MINUTES_PER_DAY) / 60;
    const toNight = hour < 19;
    this.openChoice("Campfire", "", "The fire is warm. Rest a while?", [
      {
        text: toNight ? "Rest until nightfall" : "Rest until morning",
        action: () => {
          if (toNight) {
            this.state.clock = 20 * 60;
          } else {
            this.state.clock = 6 * 60;
            this.state.day += 1;
          }
          this.ui.toast(toNight ? "Night falls over the world." : "A new day dawns.");
        },
      },
      { text: "Stay a moment longer", action: () => {} },
    ]);
  }

  // ---------------------------------------------------------------- crafting
  private doCraft(recipeId: string) {
    if (Crafting.craft(this.state, recipeId)) {
      const r = ITEMS[recipeId];
      this.ui.toast(`Crafted ${r.name}`);
      QuestSystem.refresh(this.state);
    } else {
      this.ui.toast("You lack the materials.");
    }
  }

  // ---------------------------------------------------------------- dialog
  private ctx(): DialogContext {
    return {
      state: this.state,
      give: (id, n = 1) => {
        Inventory.add(this.state, id, n);
        this.ui.toast(`+${n} ${ITEMS[id]?.name ?? id}`);
      },
      take: (id, n = 1) => Inventory.remove(this.state, id, n),
      has: (id, n = 1) => Inventory.has(this.state, id, n),
      startQuest: (id) => {
        QuestSystem.start(this.state, id);
        // Teach the recipe a quest asks the player to craft.
        if (id === "bridge") Crafting.learn(this.state, "bridgeplank");
        if (id === "ruins") Crafting.learn(this.state, "charm");
      },
      completeQuest: (id) => {
        const def = QuestSystem.complete(this.state, id);
        if (def) this.announceComplete(def);
      },
      setObjective: (q, o) => {
        if (this.state.quests[q]) this.state.quests[q].done[o] = true;
      },
      setFlag: (k, v = true) => {
        this.state.flags[k] = v as boolean;
      },
      flag: (k) => this.state.flags[k],
      toast: (m) => this.ui.toast(m),
    };
  }

  private announceComplete(def: { title: string; reward: Record<string, number> }) {
    const rewards = Object.entries(def.reward)
      .map(([id, n]) => `${n}× ${ITEMS[id]?.name ?? id}`)
      .join(", ");
    this.ui.toast(`Quest complete: ${def.title}`);
    if (rewards) this.ui.toast(`Reward: ${rewards}`);
  }

  private startDialog(npcId: string) {
    const npc = NPCS[npcId];
    const tree = npc.dialog;
    const startId = tree.start(this.state);
    this.dialog = { kind: "npc", npcId, tree, nodeId: startId };
    this.renderNpcNode();
  }

  private renderNpcNode() {
    if (!this.dialog || this.dialog.kind !== "npc") return;
    const { tree, nodeId, npcId } = this.dialog;
    const npc = NPCS[npcId];
    const node = tree.nodes[nodeId];
    const text =
      typeof node.text === "function" ? node.text(this.state) : node.text;

    this.choiceActions = [];
    const viewChoices: { text: string; disabled?: boolean }[] = [];

    if (node.choices && node.choices.length) {
      for (const ch of node.choices) {
        if (ch.cond && !ch.cond(this.state)) continue;
        viewChoices.push({ text: ch.text });
        this.choiceActions.push(() => {
          ch.effect?.(this.ctx());
          this.goTo(ch.next);
        });
      }
    } else {
      const target = node.next ?? null;
      viewChoices.push({ text: target ? "Continue" : "Farewell" });
      this.choiceActions.push(() => this.goTo(target));
    }

    this.ui.showDialog({
      speaker: npc.name,
      title: npc.title,
      text,
      choices: viewChoices,
    });
  }

  private goTo(next: string | null | undefined) {
    if (!this.dialog || this.dialog.kind !== "npc") return;
    if (next == null) {
      this.endDialog();
      return;
    }
    this.dialog.nodeId = next;
    this.renderNpcNode();
  }

  private pickChoice(i: number) {
    const action = this.choiceActions[i];
    if (action) action();
  }

  private endDialog() {
    this.dialog = null;
    this.choiceActions = [];
    this.ui.hideDialog();
    QuestSystem.refresh(this.state);
    this.save(false);
  }

  /** A simple one-line message shown in the dialog box. */
  private message(speaker: string, title: string, text: string) {
    this.openChoice(speaker, title, text, [{ text: "Close" }]);
  }

  private openChoice(
    speaker: string,
    title: string,
    text: string,
    choices: { text: string; action?: () => void }[],
  ) {
    this.dialog = { kind: "custom" };
    this.choiceActions = choices.map((c) => () => {
      c.action?.();
      this.endDialog();
    });
    this.ui.showDialog({
      speaker,
      title,
      text,
      choices: choices.map((c) => ({ text: c.text })),
    });
  }

  // ---------------------------------------------------------------- draw
  private draw() {
    const phase = phaseOf(this.state.clock);
    const npcs: RenderNPC[] = [];
    for (const npc of NPC_LIST) {
      const slot = npc.schedule[phase];
      if (!slot || slot.map !== this.state.map) continue;
      const pos = slotPos(slot)!;
      npcs.push({
        pos,
        color: npc.color,
        accent: npc.accent,
        name: npc.name,
        marker: this.npcMarker(npc.id),
        facingLeft: this.player.pos.x < pos.x,
      });
    }

    this.renderer.render({
      map: this.map,
      state: this.state,
      time: this.time,
      camera: this.camera,
      player: this.player,
      npcs,
      highlight: this.focus ? this.focus.pos : null,
      moveTarget: this.player.pathTarget,
    });

    this.ui.updateHUD(this.state, this.map.name);
    this.ui.setHint(this.hintText());
  }

  private hintText(): string {
    const active = QuestSystem.active(this.state);
    if (!active.length) {
      return "Explore Wend Village — talk to villagers marked with ✦ to find quests.";
    }
    const q = active[0];
    const next = q.objectives.find((o) => !this.state.quests[q.id].done[o.id]);
    return next ? `${q.title}: ${next.text}` : q.title;
  }

  /** Marker glyph drawn above an NPC's head. */
  private npcMarker(npcId: string): string {
    const npc = NPCS[npcId];
    const offered = Object.values(QUESTS).filter((q) => q.giver === npc.name);
    for (const q of offered) {
      if (this.state.quests[q.id]?.status === "available") return "!";
    }
    for (const q of offered) {
      if (this.state.quests[q.id]?.status === "active" && this.turnInReady(q.id))
        return "?";
    }
    return "";
  }

  private turnInReady(questId: string): boolean {
    const s = this.state;
    switch (questId) {
      case "tonics":
        return Inventory.has(s, "potion", 2);
      case "locket":
        return Inventory.has(s, "locket");
      case "letter":
        return Boolean(s.flags.letter_delivered) && !s.flags.letter_replied;
      default:
        return false;
    }
  }

  // ---------------------------------------------------------------- save
  private save(flash: boolean) {
    if (!this.started) return;
    const ok = SaveSystem.save(cloneState(this.state));
    if (ok && flash) this.ui.flashSaved();
  }
}
