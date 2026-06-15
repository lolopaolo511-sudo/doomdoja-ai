import type { GameState } from "../core/types";
import { ITEMS } from "../data/items";
import { QUESTS } from "../data/quests";
import { Crafting } from "../systems/Crafting";
import { Inventory } from "../systems/Inventory";
import { QuestSystem } from "../systems/QuestSystem";
import { formatClock, phaseLabel, phaseOf } from "../world/DayNight";

export interface DialogView {
  speaker: string;
  title: string;
  text: string;
  choices: { text: string; disabled?: boolean }[];
}

export interface UIHandlers {
  hasSave(): boolean;
  newGame(): void;
  continueGame(): void;
  pickChoice(index: number): void;
  craft(recipeId: string): void;
  save(): void;
  resume(): void;
  toMenu(): void;
  closePanel(): void;
}

export type SatchelTab = "inventory" | "crafting" | "quests";

/** Owns every DOM overlay: menu, HUD, dialog, satchel, pause, toasts. */
export class UI {
  root: HTMLElement;
  private h: UIHandlers;

  constructor(root: HTMLElement, handlers: UIHandlers) {
    this.root = root;
    this.h = handlers;
    root.innerHTML = TEMPLATE;
    this.wire();
  }

  // --- element shortcuts ---
  private el<T extends HTMLElement = HTMLElement>(id: string): T {
    return this.root.querySelector(`#${id}`) as T;
  }

  private wire() {
    this.el("btn-new").addEventListener("click", () => this.h.newGame());
    this.el("btn-continue").addEventListener("click", () => this.h.continueGame());
    this.el("btn-resume").addEventListener("click", () => this.h.resume());
    this.el("btn-save").addEventListener("click", () => this.h.save());
    this.el("btn-quit").addEventListener("click", () => this.h.toMenu());
    this.el("panel-close").addEventListener("click", () => this.h.closePanel());

    for (const tab of ["inventory", "crafting", "quests"] as SatchelTab[]) {
      this.el(`tab-${tab}`).addEventListener("click", () => {
        this.activeTab = tab;
        this.renderSatchel(this.lastState!);
      });
    }

    // HUD buttons
    this.el("hud-inv").addEventListener("click", () => this.requestSatchel?.("inventory"));
    this.el("hud-craft").addEventListener("click", () => this.requestSatchel?.("crafting"));
    this.el("hud-quest").addEventListener("click", () => this.requestSatchel?.("quests"));
    this.el("hud-menu").addEventListener("click", () => this.requestPause?.());
  }

  /** Set by Game so HUD buttons can open panels. */
  requestSatchel?: (tab: SatchelTab) => void;
  requestPause?: () => void;

  // ---------------------------------------------------------------- menu
  showMenu() {
    this.el("menu").classList.remove("hidden");
    (this.el("btn-continue") as HTMLButtonElement).disabled = !this.h.hasSave();
    this.el("btn-continue").classList.toggle("opacity-40", !this.h.hasSave());
  }
  hideMenu() {
    this.el("menu").classList.add("hidden");
  }

  // ---------------------------------------------------------------- HUD
  setHudVisible(v: boolean) {
    this.el("hud").classList.toggle("hidden", !v);
  }

  updateHUD(state: GameState, locationName: string) {
    const phase = phaseOf(state.clock);
    this.el("hud-loc").textContent = locationName;
    this.el("hud-clock").textContent = formatClock(state.clock);
    this.el("hud-phase").textContent = `${phaseLabel(phase)} · Day ${state.day}`;
    const icon: Record<string, string> = { dawn: "🌅", day: "☀️", dusk: "🌇", night: "🌙" };
    this.el("hud-icon").textContent = icon[phase];
    const active = QuestSystem.active(state).length;
    this.el("hud-quest-count").textContent = active ? String(active) : "";
    this.el("hud-quest-count").classList.toggle("hidden", active === 0);
  }

  setHint(text: string) {
    const e = this.el("hint");
    e.textContent = text;
    e.classList.toggle("opacity-0", text === "");
  }

  setInteractPrompt(text: string | null) {
    const e = this.el("prompt");
    if (!text) {
      e.classList.add("hidden");
    } else {
      e.classList.remove("hidden");
      this.el("prompt-text").textContent = text;
    }
  }

  // ---------------------------------------------------------------- dialog
  showDialog(view: DialogView) {
    this.el("dialog").classList.remove("hidden");
    this.el("dlg-speaker").textContent = view.speaker;
    this.el("dlg-title").textContent = view.title;
    const textEl = this.el("dlg-text");
    textEl.textContent = view.text;
    const choices = this.el("dlg-choices");
    choices.innerHTML = "";
    view.choices.forEach((c, i) => {
      const b = document.createElement("button");
      b.className =
        "btn w-full text-left !justify-start text-sm md:text-base " +
        (c.disabled ? "opacity-40 pointer-events-none" : "");
      b.textContent = `${i + 1}.  ${c.text}`;
      b.addEventListener("click", () => this.h.pickChoice(i));
      choices.appendChild(b);
    });
  }
  hideDialog() {
    this.el("dialog").classList.add("hidden");
  }
  isDialogOpen() {
    return !this.el("dialog").classList.contains("hidden");
  }

  // ---------------------------------------------------------------- satchel
  private activeTab: SatchelTab = "inventory";
  private lastState: GameState | null = null;

  openSatchel(tab: SatchelTab, state: GameState) {
    this.activeTab = tab;
    this.el("panel").classList.remove("hidden");
    this.renderSatchel(state);
  }
  closeSatchel() {
    this.el("panel").classList.add("hidden");
  }
  isSatchelOpen() {
    return !this.el("panel").classList.contains("hidden");
  }

  renderSatchel(state: GameState) {
    this.lastState = state;
    for (const t of ["inventory", "crafting", "quests"] as SatchelTab[]) {
      const on = t === this.activeTab;
      const tab = this.el(`tab-${t}`);
      tab.classList.toggle("bg-aether-gold", on);
      tab.classList.toggle("text-aether-ink", on);
      tab.classList.toggle("text-aether-muted", !on);
    }
    const body = this.el("panel-body");
    if (this.activeTab === "inventory") body.innerHTML = this.invHTML(state);
    else if (this.activeTab === "crafting") body.innerHTML = this.craftHTML(state);
    else body.innerHTML = this.questHTML(state);

    if (this.activeTab === "crafting") {
      body.querySelectorAll<HTMLButtonElement>("[data-craft]").forEach((b) => {
        b.addEventListener("click", () => {
          this.h.craft(b.dataset.craft!);
          this.renderSatchel(this.lastState!);
        });
      });
    }
  }

  private invHTML(state: GameState): string {
    const entries = Inventory.entries(state);
    if (!entries.length) {
      return `<p class="text-aether-muted italic px-2 py-8 text-center">Your satchel is empty. Gather herbs, wood, shards and silk out in the world.</p>`;
    }
    const cells = entries
      .map(([id, n]) => {
        const it = ITEMS[id];
        if (!it) return "";
        return `<div class="panel !rounded-xl p-3 flex gap-3 items-center">
          <div class="text-2xl w-10 h-10 grid place-items-center rounded-lg"
               style="background:${it.color}22;border:1px solid ${it.color}55">${it.glyph}</div>
          <div class="min-w-0">
            <div class="flex items-baseline gap-2">
              <span class="title-font text-aether-text">${it.name}</span>
              <span class="chip">×${n}</span>
            </div>
            <div class="text-xs text-aether-muted leading-snug">${it.desc}</div>
          </div>
        </div>`;
      })
      .join("");
    return `<div class="grid sm:grid-cols-2 gap-2">${cells}</div>`;
  }

  private craftHTML(state: GameState): string {
    const recipes = Crafting.knownRecipes(state);
    const rows = recipes
      .map((r) => {
        const can = Crafting.canCraft(state, r.id);
        const inputs = Object.entries(r.inputs)
          .map(([id, need]) => {
            const have = Inventory.count(state, id);
            const ok = have >= need;
            const it = ITEMS[id];
            return `<span class="chip ${ok ? "!text-aether-text !border-aether-gold/60" : "!text-red-300/80"}">
              ${it?.glyph ?? ""} ${it?.name ?? id} ${have}/${need}</span>`;
          })
          .join(" ");
        const res = ITEMS[r.result];
        return `<div class="panel !rounded-xl p-3">
          <div class="flex items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <div class="text-2xl w-10 h-10 grid place-items-center rounded-lg"
                   style="background:${res.color}22;border:1px solid ${res.color}55">${res.glyph}</div>
              <div>
                <div class="title-font">${r.name}</div>
                <div class="text-xs text-aether-muted">${r.desc}</div>
              </div>
            </div>
            <button data-craft="${r.id}" class="${can ? "btn-primary" : "btn"} text-sm" ${can ? "" : "disabled"}>Craft</button>
          </div>
          <div class="mt-2 flex flex-wrap gap-1">${inputs}</div>
        </div>`;
      })
      .join("");
    return `<div class="space-y-2">${rows}</div>`;
  }

  private questHTML(state: GameState): string {
    const active = QuestSystem.active(state);
    const done = QuestSystem.completed(state);
    if (!active.length && !done.length) {
      return `<p class="text-aether-muted italic px-2 py-8 text-center">No quests yet. Talk to the villagers — look for a golden “!” above their heads.</p>`;
    }
    const activeHTML = active
      .map((q) => {
        const st = state.quests[q.id];
        const objs = q.objectives
          .map((o) => {
            const ok = st.done[o.id];
            return `<li class="flex gap-2 items-start text-sm ${ok ? "text-aether-muted line-through" : "text-aether-text"}">
              <span class="mt-0.5">${ok ? "✔" : "○"}</span><span>${o.text}</span></li>`;
          })
          .join("");
        return `<div class="panel !rounded-xl p-3">
          <div class="flex items-center justify-between">
            <span class="title-font text-aether-gold">${q.title}</span>
            <span class="chip">${q.giver}</span>
          </div>
          <p class="text-xs text-aether-muted my-1">${q.summary}</p>
          <ul class="space-y-1 mt-2">${objs}</ul>
        </div>`;
      })
      .join("");
    const doneHTML = done.length
      ? `<div class="mt-3">
          <div class="text-xs uppercase tracking-widest text-aether-muted mb-1 px-1">Completed</div>
          ${done
            .map(
              (q) =>
                `<div class="panel !rounded-xl p-2 px-3 flex items-center justify-between opacity-70">
                   <span class="title-font text-sm">✔ ${q.title}</span>
                   <span class="chip">${QUESTS[q.id].giver}</span>
                 </div>`,
            )
            .join("")}
        </div>`
      : "";
    return `<div class="space-y-2">${activeHTML}${doneHTML}</div>`;
  }

  // ---------------------------------------------------------------- pause
  showPause() {
    this.el("pause").classList.remove("hidden");
  }
  hidePause() {
    this.el("pause").classList.add("hidden");
  }
  isPauseOpen() {
    return !this.el("pause").classList.contains("hidden");
  }

  flashSaved() {
    const e = this.el("save-flash");
    e.classList.remove("opacity-0");
    setTimeout(() => e.classList.add("opacity-0"), 1200);
  }

  // ---------------------------------------------------------------- toasts
  toast(msg: string) {
    const wrap = this.el("toasts");
    const t = document.createElement("div");
    t.className =
      "panel !rounded-xl px-4 py-2 text-sm text-aether-text animate-fadein shadow-lg";
    t.innerHTML = `<span class="text-aether-gold mr-1">✦</span>${msg}`;
    wrap.appendChild(t);
    setTimeout(() => {
      t.style.transition = "opacity .4s, transform .4s";
      t.style.opacity = "0";
      t.style.transform = "translateX(20px)";
      setTimeout(() => t.remove(), 400);
    }, 2800);
  }
}

const TEMPLATE = /* html */ `
<canvas id="game"></canvas>
<div class="vignette"></div>

<!-- HUD -->
<div id="hud" class="hidden absolute inset-0 pointer-events-none select-none">
  <div class="absolute top-3 left-3 panel !rounded-xl px-3 py-2 flex items-center gap-3 pointer-events-auto">
    <span id="hud-icon" class="text-xl">☀️</span>
    <div>
      <div id="hud-loc" class="title-font text-aether-gold leading-none">Wend Village</div>
      <div class="flex items-baseline gap-2">
        <span id="hud-clock" class="text-lg leading-none">08:00</span>
        <span id="hud-phase" class="text-xs text-aether-muted">Day · Day 1</span>
      </div>
    </div>
  </div>

  <div class="absolute top-3 right-3 flex gap-2 pointer-events-auto">
    <button id="hud-inv" class="btn !px-3 !py-2" title="Inventory (I)">🎒</button>
    <button id="hud-craft" class="btn !px-3 !py-2" title="Crafting (C)">⚒️</button>
    <button id="hud-quest" class="btn !px-3 !py-2 relative" title="Quests (J)">📜
      <span id="hud-quest-count" class="hidden absolute -top-1 -right-1 bg-aether-gold text-aether-ink text-[10px] rounded-full w-4 h-4 grid place-items-center">0</span>
    </button>
    <button id="hud-menu" class="btn !px-3 !py-2" title="Menu (Esc)">☰</button>
  </div>

  <div id="prompt" class="hidden absolute left-1/2 -translate-x-1/2 bottom-24 panel !rounded-full px-4 py-2 text-sm animate-pop">
    <span class="text-aether-gold font-bold">E</span> / click — <span id="prompt-text">interact</span>
  </div>

  <div id="hint" class="absolute left-1/2 -translate-x-1/2 bottom-3 text-xs text-aether-muted transition-opacity duration-500"></div>
  <div id="save-flash" class="absolute bottom-3 right-3 text-xs text-aether-gold opacity-0 transition-opacity">✓ Saved</div>
</div>

<!-- Dialog -->
<div id="dialog" class="hidden absolute inset-x-0 bottom-0 p-3 md:p-6 flex justify-center">
  <div class="panel w-full max-w-2xl p-5 animate-fadein">
    <div class="flex items-baseline gap-2 mb-1">
      <span id="dlg-speaker" class="title-font text-lg text-aether-gold">Name</span>
      <span id="dlg-title" class="chip">title</span>
    </div>
    <p id="dlg-text" class="text-aether-text leading-relaxed mb-4 min-h-[3.5rem]"></p>
    <div id="dlg-choices" class="space-y-2"></div>
  </div>
</div>

<!-- Satchel panel -->
<div id="panel" class="hidden absolute inset-0 bg-black/40 grid place-items-center p-4">
  <div class="panel w-full max-w-2xl max-h-[88vh] flex flex-col animate-pop">
    <div class="flex items-center gap-2 p-3 border-b border-aether-edge">
      <button id="tab-inventory" class="btn !py-1.5 text-sm">🎒 Inventory</button>
      <button id="tab-crafting" class="btn !py-1.5 text-sm">⚒️ Crafting</button>
      <button id="tab-quests" class="btn !py-1.5 text-sm">📜 Quests</button>
      <div class="flex-1"></div>
      <button id="panel-close" class="btn !px-3 !py-1.5 text-sm">✕</button>
    </div>
    <div id="panel-body" class="p-4 overflow-y-auto scroll-thin"></div>
  </div>
</div>

<!-- Pause -->
<div id="pause" class="hidden absolute inset-0 bg-black/55 grid place-items-center">
  <div class="panel p-6 w-72 animate-pop text-center">
    <div class="title-font text-2xl text-aether-gold mb-4">Paused</div>
    <div class="space-y-2">
      <button id="btn-resume" class="btn-primary w-full">Resume</button>
      <button id="btn-save" class="btn w-full">Save Game</button>
      <button id="btn-quit" class="btn w-full">Main Menu</button>
    </div>
  </div>
</div>

<!-- Main menu -->
<div id="menu" class="absolute inset-0 grid place-items-center bg-gradient-to-b from-[#0a1430] via-[#0d0f1a] to-[#05060c]">
  <div class="text-center animate-fadein px-6">
    <div class="title-font text-6xl md:text-7xl text-aether-gold tracking-[0.2em] drop-shadow-[0_0_30px_rgba(232,200,122,0.35)]">AETHERFALL</div>
    <p class="text-aether-muted mt-3 italic">A small living world, fallen from the sky.</p>
    <div class="mt-8 flex flex-col items-center gap-3">
      <button id="btn-new" class="btn-primary w-60 text-lg">New Game</button>
      <button id="btn-continue" class="btn w-60 text-lg">Continue</button>
    </div>
    <div class="mt-10 text-xs text-aether-muted/80 max-w-md mx-auto leading-relaxed">
      Move with <b>WASD</b> / arrows or <b>click</b>. Talk &amp; gather with <b>E</b> / click.
      <b>I</b> inventory · <b>C</b> crafting · <b>J</b> quests · <b>Esc</b> menu.
    </div>
  </div>
</div>

<!-- Toasts -->
<div id="toasts" class="absolute top-20 right-3 space-y-2 w-64 pointer-events-none"></div>
`;
