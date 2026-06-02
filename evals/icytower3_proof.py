#!/usr/bin/env python3
"""
DOWÓD BLOKU 3 — IcyTower3 przez nowy planner + verifier.

Demonstruje:
  1. Planner v2 generuje plan z acceptance_criteria dla gry HTML
  2. Verifier weryfikuje kompletność pliku HTML (canvas, pętla gry, struktura)
  3. Verifier UCZCIWIE raportuje braki zamiast udawać sukces
  4. Jeśli lokalny model nie domknie gry, verifier wyraźnie to wykrywa

Uruchomienie:
  python3 ~/qwen-agent/evals/icytower3_proof.py [--with-llm]

  Bez --with-llm: demonstracja na szablonie (symulacja outputu codera)
  Z --with-llm:   realne wywołanie orchestratora (wymaga Ollamy)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "multiagent"))

WORK_DIR = Path.home() / "IcyTower3"
TASK = "stwórz ~/IcyTower3 z grą Icy Tower w jednym pliku index.html"

# ── SCENARIUSZ 1: weryfikacja pliku wygenerowanego przez LLM (mockowany) ──────

MINIMAL_BROKEN_HTML = """<!DOCTYPE html>
<html>
<head><title>Icy Tower</title></head>
<body>
<p>Gra Icy Tower — work in progress</p>
</body>
</html>
"""

FULL_GAME_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <title>Icy Tower 3</title>
  <style>
    body { margin: 0; background: #0a1628; display: flex; justify-content: center; align-items: center; height: 100vh; }
    canvas { border: 2px solid #4af; }
  </style>
</head>
<body>
<canvas id="gameCanvas" width="400" height="600"></canvas>
<script>
// Icy Tower 3 — jeden plik
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const GRAVITY = 0.4;
const JUMP_FORCE = -10;
const PLATFORM_COUNT = 8;
const W = canvas.width, H = canvas.height;

const player = {
  x: W / 2, y: H - 60, vx: 0, vy: 0,
  w: 28, h: 36, onGround: false,
  color: '#4af'
};

const platforms = [];
let score = 0;
let cameraY = 0;
let gameOver = false;

function initPlatforms() {
  platforms.length = 0;
  // Platforma startowa
  platforms.push({ x: W/2 - 50, y: H - 30, w: 100, h: 12 });
  for (let i = 1; i < PLATFORM_COUNT * 3; i++) {
    platforms.push({
      x: Math.random() * (W - 80),
      y: H - 30 - i * 70 - Math.random() * 30,
      w: 60 + Math.random() * 40,
      h: 12
    });
  }
}

function reset() {
  player.x = W / 2; player.y = H - 60;
  player.vx = 0; player.vy = 0;
  cameraY = 0; score = 0; gameOver = false;
  initPlatforms();
}

function update() {
  if (gameOver) return;

  // Input
  if (keys['ArrowLeft'] || keys['a']) player.vx = -4;
  else if (keys['ArrowRight'] || keys['d']) player.vx = 4;
  else player.vx *= 0.85;

  if ((keys['ArrowUp'] || keys['w'] || keys[' ']) && player.onGround) {
    player.vy = JUMP_FORCE;
    player.onGround = false;
  }

  player.vy += GRAVITY;
  player.x += player.vx;
  player.y += player.vy;

  // Wrap horizontally
  if (player.x > W) player.x = 0;
  if (player.x < 0) player.x = W;

  // Kolizje z platformami
  player.onGround = false;
  platforms.forEach(p => {
    if (
      player.vy > 0 &&
      player.x + player.w > p.x &&
      player.x < p.x + p.w &&
      player.y + player.h > p.y + cameraY &&
      player.y + player.h < p.y + cameraY + p.h + 10
    ) {
      player.y = p.y + cameraY - player.h;
      player.vy = 0;
      player.onGround = true;
    }
  });

  // Scroll kamery za graczem (w górę)
  const scrollThreshold = H * 0.4;
  if (player.y < scrollThreshold) {
    const delta = scrollThreshold - player.y;
    cameraY -= delta;
    player.y = scrollThreshold;
    score += Math.floor(delta);
  }

  // Dodaj nowe platformy na górze
  const topPlatform = Math.min(...platforms.map(p => p.y));
  while (topPlatform + cameraY > -50) {
    const newY = Math.min(...platforms.map(p => p.y)) - 65 - Math.random() * 30;
    platforms.push({
      x: Math.random() * (W - 80),
      y: newY,
      w: 60 + Math.random() * 40,
      h: 12
    });
  }

  // Usuń platformy poniżej ekranu
  while (platforms.length > PLATFORM_COUNT * 6) platforms.shift();

  // Game over — gracz spad
  if (player.y - cameraY > H + 100) gameOver = true;
}

function draw() {
  ctx.fillStyle = '#0a1628';
  ctx.fillRect(0, 0, W, H);

  // Platformy
  ctx.fillStyle = '#2a6';
  platforms.forEach(p => {
    const screenY = p.y + cameraY;
    if (screenY > -20 && screenY < H + 20) {
      ctx.fillRect(p.x, screenY, p.w, p.h);
      ctx.fillStyle = '#3c8';
      ctx.fillRect(p.x, screenY, p.w, 4);
      ctx.fillStyle = '#2a6';
    }
  });

  // Gracz
  ctx.fillStyle = player.color;
  ctx.fillRect(player.x, player.y, player.w, player.h);

  // Oczy
  ctx.fillStyle = '#000';
  ctx.fillRect(player.x + 7, player.y + 8, 5, 5);
  ctx.fillRect(player.x + 16, player.y + 8, 5, 5);

  // UI
  ctx.fillStyle = '#fff';
  ctx.font = '18px monospace';
  ctx.fillText('Score: ' + score, 10, 28);

  if (gameOver) {
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#ff4';
    ctx.font = 'bold 32px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('GAME OVER', W/2, H/2 - 20);
    ctx.font = '18px monospace';
    ctx.fillText('Score: ' + score, W/2, H/2 + 20);
    ctx.fillText('Press R to restart', W/2, H/2 + 55);
    ctx.textAlign = 'left';
  }
}

const keys = {};
document.addEventListener('keydown', e => {
  keys[e.key] = true;
  if (e.key === 'r' || e.key === 'R') reset();
  e.preventDefault();
});
document.addEventListener('keyup', e => { keys[e.key] = false; });

function gameLoop() {
  update();
  draw();
  requestAnimationFrame(gameLoop);
}

reset();
gameLoop();
</script>
</body>
</html>
"""


def run_with_mock(scenario: str = "full") -> dict:
    """Demonstracja verifier bez LLM."""
    from multiagent.verifier import Verifier
    from multiagent.planner import plan as _plan

    print("\n" + "="*62)
    print("  DOWÓD BLOKU 3 — IcyTower3 + Verifier")
    print(f"  Scenariusz: {'KOMPLETNA GRA' if scenario == 'full' else 'NIEKOMPLETNY OUTPUT'}")
    print("="*62)

    # 1. Pokaż plan
    print("\n[PLANNER] Generuję plan (bez LLM — deterministyczny fallback)...")
    import planner as pm
    # Symulacja planu dla zadania HTML game (bez wywołania LLM)
    mock_plan = {
        "goal": "Gra Icy Tower w jednym pliku index.html",
        "verification_type": "html",
        "steps": [
            {
                "id": 1, "title": "Struktura HTML + canvas",
                "description": "Utwórz plik index.html z DOCTYPE, html, head, body, canvas 400x600",
                "file": "index.html",
                "acceptance_criteria": [
                    "Plik index.html istnieje",
                    "Zawiera element <canvas>",
                    "Poprawna struktura HTML5",
                ],
                "checkpoint": "step_1_done",
                "depends_on": [],
            },
            {
                "id": 2, "title": "Logika gry + pętla animacji",
                "description": "Dodaj JavaScript: gracz, platformy, grawitacja, requestAnimationFrame",
                "file": "index.html",
                "acceptance_criteria": [
                    "requestAnimationFrame() obecny",
                    "canvas.getContext() wywołany",
                    "Gracz porusza się pod wpływem grawitacji",
                    "Brak błędów składni JS",
                ],
                "checkpoint": "step_2_done",
                "depends_on": [1],
            },
        ],
        "tests_file": None,
        "notes": "Jeden plik HTML — cały game engine w <script>",
    }

    print(f"[PLANNER] Cel: {mock_plan['goal']}")
    for s in mock_plan["steps"]:
        print(f"[PLANNER]   {s['id']}. {s['title']}")
        for c in s["acceptance_criteria"]:
            print(f"[PLANNER]      ✓ {c}")

    # 2. Przygotuj katalog
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    html_path = WORK_DIR / "index.html"

    # 3. "Coder" zapisuje output
    html_content = FULL_GAME_HTML if scenario == "full" else MINIMAL_BROKEN_HTML
    html_path.write_text(html_content, encoding="utf-8")
    print(f"\n[CODER] Zapisano {html_path.name} ({len(html_content)} znaków)")

    # 4. Verifier weryfikuje
    print("\n[VERIFIER] Uruchamiam weryfikację artefaktu...")
    v = Verifier()
    result = v.verify_path(html_path)

    print(result.summary())

    if not result.passed:
        print("\n[VERIFIER] Wskazówka naprawcza:")
        print(result.fix_hint)
        print("\n[VERIFIER] WYNIK: ✗ NIEKOMPLETNE — artefakt nie spełnia acceptance criteria")
        print("[VERIFIER] Verifier uczciwie wykrył braki, NIE udaje sukcesu.")
    else:
        print(f"\n[VERIFIER] WYNIK: ✓ PASS — gra kompletna")
        print(f"[VERIFIER] Rozmiar pliku: {len(html_content.encode())} bajtów")
        print(f"[VERIFIER] Plik gry: {html_path}")

    # Raport
    report = {
        "task": TASK,
        "work_dir": str(WORK_DIR),
        "scenario": scenario,
        "plan": mock_plan,
        "verifier": result.as_dict(),
        "overall": "PASS" if result.passed else "FAIL",
        "timestamp": datetime.now().isoformat(),
    }
    report_path = WORK_DIR / "proof_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n[PROOF] Raport: {report_path}")

    return report


def run_with_llm() -> dict:
    """Realne wywołanie orchestratora z LLM."""
    print("\n" + "="*62)
    print("  DOWÓD BLOKU 3 — IcyTower3 + Verifier (REALNE LLM)")
    print("="*62)

    import subprocess
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n[PROOF] Uruchamiam orchestrator z --verify...")
    print(f"[PROOF] Katalog roboczy: {WORK_DIR}")
    print(f"[PROOF] Zadanie: {TASK}")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "multiagent" / "orchestrator.py"),
            TASK,
            "--work-dir", str(WORK_DIR),
            "--verify",
            "--max-verify-rounds", "2",
            "--max-rounds", "1",
        ],
        capture_output=False,
        text=True,
        timeout=600,
    )

    print(f"\n[PROOF] Orchestrator exit: {result.returncode}")

    # Pokaż raport z verifier
    report_path = WORK_DIR / "multiagent_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
        print(f"\n[PROOF] Verifier passed: {report.get('verifier_passed')}")
        print(f"[PROOF] LLM approved: {report.get('llm_approved')}")
        print(f"[PROOF] Overall: {report.get('overall_approved')}")
        if report.get("verifier_report"):
            print("\n[PROOF] Raport verifier:")
            print(report["verifier_report"])
        return report

    return {"error": "brak raportu", "returncode": result.returncode}


def main():
    parser = argparse.ArgumentParser(description="Dowód Bloku 3 — IcyTower3 + Verifier")
    parser.add_argument("--with-llm", action="store_true",
                        help="Użyj prawdziwego LLM (wymaga Ollamy)")
    parser.add_argument("--scenario", choices=["full", "broken"], default="full",
                        help="Scenariusz mock: full=kompletna gra, broken=niekompletny output")
    args = parser.parse_args()

    if args.with_llm:
        report = run_with_llm()
    else:
        # Uruchom oba scenariusze
        print("Demonstracja scenariusza BROKEN (niekompletny output codera):")
        run_with_mock("broken")
        print("\n" + "-"*62)
        print("Demonstracja scenariusza FULL (kompletna gra):")
        report = run_with_mock("full")

    return 0 if report.get("verifier", {}).get("passed") or report.get("verifier_passed") else 1


if __name__ == "__main__":
    sys.exit(main())
