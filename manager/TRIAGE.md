# Reguły triażu — 3-poziomowy podział EASY / MEDIUM / HARD

> Wersja: 2026-06-04 | Źródło prawdy dla `classify_level()` w `level.py`

---

## Polityka per poziom

| Poziom | Ikona | Polityka daemona |
|--------|-------|-----------------|
| **EASY** | 🟢 | Lokalny model bez eskalacji. Verifier opcjonalny (wystarczy niepusta odpowiedź). |
| **MEDIUM** | 🟡 | Lokalny NAJPIERW. Verifier sprawdza wynik. Jeśli fail po N rundach (domyślnie 2) → eskalacja przez router do cloud. |
| **HARD** | 🔴 | Od razu `needs_escalation` w outbox. Bez marnowania rund lokalnie. Uzasadnienie w polu `escalation_reason`. |

Pole `mode: local` w zadaniu wymusza EASY (niezależnie od klasyfikacji).

---

## Tabela decyzji EASY / MEDIUM / HARD

### 🟢 EASY — Lokalny model, bez eskalacji

| Kategoria | Przykłady |
|-----------|-----------|
| **Prosta funkcja** | `licz_vat(netto, stawka)`, sortowanie, regex, transformacja stringa |
| **CRUD / parser** | parser CSV/JSON, insert/select SQLite, walidator pola |
| **Test jednostkowy** | pytest dla gotowej funkcji, fixture, mock prostej zależności |
| **Konfigi / boilerplate** | `.gitignore`, `Dockerfile` wg szablonu, env przykład, `pyproject.toml` |
| **Scraping wg schematu** | Playwright wg gotowego selektora, ekstrakcja pola ze strony |
| **Formatowanie / raport** | tabela Markdown, eksport do CSV, prosty wykres matplotlib |
| **Dokumentacja** | docstring, komentarze do istniejącego kodu, README sekcja |
| **Bash / shell** | prosty skrypt, one-liner, cron entry, launchd plist |
| **Dane prywatne** | zadanie z hasłem / tokenem / PESEL — wymuszone local-only |

**Sygnały → EASY:** `prosty`, `test`, `pytest`, `parser`, `crud`, `config`, `szablon`, `one-liner`, `docstring`, `rename`, `przelicz`, `pojedyncz`, `1 plik`

---

### 🟡 MEDIUM — Lokalny NAJPIERW, escalate po failach

| Kategoria | Przykłady |
|-----------|-----------|
| **Moduł/klasa kilkuplikowa** | klasa z metodami + testy + przykład użycia |
| **Pipeline prosty** | kilka kroków liniowych, pipeline z 2–3 etapami |
| **Refaktor modułu ≤200 linii** | ekstrakcja funkcji, przepisanie klasy, zmiana interfejsu |
| **Integracja z jednym API** | wrapper API wg dokumentacji, klient HTTP z obsługą błędów |
| **Debugging standardowy** | błąd z traceback, jednoetapowy, odtwarzalny lokalnie |
| **Zadanie wieloetapowe** | „najpierw X, potem Y, na końcu Z" — 3–4 kroki, znane wzorce |
| **Skrypt na live (niskie ryzyko)** | skrypt analityczny na live env (read-only) |

**Sygnały → MEDIUM:** `pipeline`, `multi-step`, `kilka kroków`, `klasa`, `moduł`, `refaktor`, `integracja`, `wrapper`, `debugging`, `najpierw… potem`

---

### 🔴 HARD — Natychmiastowa eskalacja (needs_escalation)

| Kategoria | Przykłady |
|-----------|-----------|
| **Architektura** | projektowanie mikroserwisów, schemat DB nowego projektu, decyzja tech-stack |
| **Debugging złożony** | race condition, memory leak, problem w >3 plikach, nie odtwarzalny |
| **Produkcja / wysoka stawka** | kod na live, migracja bazy z danymi, breaking change, deploy na prod |
| **Wieloplikowy refaktor** | przepisanie modułu >500 linii, zmiana publicznych interfejsów |
| **Analiza i strategia** | code review całego PR, ocena ryzyka, roadmapa, propozycja architektury |
| **Nowość** | algorytm bez wzorca, integracja bez dokumentacji, nowy protokół |
| **Pełen kontekst projektu** | „przejrzyj cały repo", „wszystkie moduły", „pełen kontekst" |

**Sygnały → HARD:** `architektur`, `zaprojektuj`, `na produkcji`, `live`, `migracja bazy`, `race condition`, `cały projekt`, `breaking change`, `wymyśl od zera`, `innowac`, `deploy na prod`

---

## Scoring — jak oblicza się poziom

```
score = 0
+ typ analityczny (+2/hit, max +4)
- typ mechaniczny (-1/hit, max -2)
+ zakres szeroki  (+2/hit, max +4)
- zakres wąski    (-1/hit, max -2)
+ trudna weryfikacja (+2/hit, max +4)
- łatwa weryfikacja  (-1/hit, max -2)  ← test/pytest obniża
+ wieloetapowe   (+1/hit, max +3)
+ nowość         (+3/hit, max +3)
+ stawka         (+4/hit, max +4)  ← "produkcja/live" mocno podnosi
+ duży kontekst  (+2/hit, max +2)
+ długość >800 znaków  +2
+ długość >400 znaków  +1

EASY   → score < 4
MEDIUM → score 4–6
HARD   → score ≥ 7
```

Progi są **konfigurowalne** i **kalibrowane** na podstawie danych historycznych.

---

## Kalibracja automatyczna

Daemon co 20 zadań uruchamia kalibrację (`level_calibration.py`):

| Obserwacja | Zmiana |
|------------|--------|
| MEDIUM local rate ≥ 80% przez ≥5 próbek | Obniż próg MEDIUM (więcej zadań jako EASY) |
| MEDIUM local rate ≤ 40% przez ≥5 próbek | Obniż próg HARD (więcej jako HARD/eskaluj) |
| Cloud uplift < 10pp dla MEDIUM | Loguj ostrzeżenie — eskalacja nie przynosi wartości |
| EASY local rate < 60% | Ostrzeżenie — sprawdź scoring |

Progi zapisywane do: `manager/level_calibration_state.json`

Ręczna kalibracja + raport:
```bash
python3 ~/qwen-agent/manager/report.py --calibrate
python3 ~/qwen-agent/manager/report.py --dry-run   # podgląd bez zapisu
```

---

## Polityka prywatności

Każde zadanie zawierające słowa: `hasło`, `password`, `token`, `secret`, `api_key`,
`PESEL`, `klucz api`, `private key`, `bearer` → **wymuszone EASY/local** niezależnie od score.
Dane wrażliwe **nigdy** nie trafiają do cloud.

---

## Użycie w kodzie

```python
from manager.level import classify_level

r = classify_level("napisz funkcję licz_vat z testem pytest")
print(r.summary())   # 🟢 EASY (score=0) — werif:test,pytest

r = classify_level("zaprojektuj architekturę na produkcji")
print(r.summary())   # 🔴 HARD (score=8) — anal:architektur | stawka:na produkcji

r = classify_level("debuguj pipeline na live")
print(r.summary())   # 🟡 MEDIUM (score=5) — multistep:pipeline | stawka:live
```

Pełny raport skuteczności:
```bash
python3 ~/qwen-agent/manager/report.py
```
