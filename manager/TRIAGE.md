# Reguły triażu — co lokalnie, co eskalować

> Wersja: 2026-06-04 | Źródło prawdy dla `classify_task()` w `triage.py`

---

## Zasada ogólna

**Lokalnie** = zadanie jest dobrze określone, mechaniczne, ma jasny schemat wejście→wyjście.  
**Eskaluj** = zadanie wymaga oceny, doświadczenia architektonicznego lub jest wysokiej stawki.

Gdy wątpliwe → **lokalnie najpierw**, weryfikator sprawdzi wynik. Jeśli fail → auto-eskalacja.

---

## Tabela decyzji

| Kategoria | Przykłady | Decyzja |
|-----------|-----------|---------|
| **Skrypty CRUD** | parser CSV/JSON, insert/select SQLite, walidator danych, konwerter formatów | 🏠 LOCAL |
| **Prosta funkcja** | obliczenia matematyczne, regex, transformacja stringa, sortowanie | 🏠 LOCAL |
| **Testy jednostkowe** | pytest dla gotowej funkcji, fixture, mock prostej zależności | 🏠 LOCAL |
| **Konfigi i boilerplate** | `.gitignore`, `pyproject.toml`, `Dockerfile` wg szablonu, env przykład | 🏠 LOCAL |
| **Scraping wg schematu** | Playwright/httpx wg gotowego selektora, ekstrakcja pola ze strony | 🏠 LOCAL |
| **Raporty i formatowanie** | tabela Markdown, generowanie PDF/Excel z danych, wykres matplotlib | 🏠 LOCAL |
| **Refaktor lokalny** | zmiana nazw, ekstrakcja funkcji, usunięcie duplikacji w <200 linii | 🏠 LOCAL |
| **Prosty moduł** | klasa dataclass, helper utils, wrapper API wg przykładu | 🏠 LOCAL |
| **Dokumentacja inline** | docstring, komentarze do istniejącego kodu, README sekcja | 🏠 LOCAL |
| **Bash/shell** | prosty skrypt, one-liner, cron entry, launchd plist wg szablonu | 🏠 LOCAL |
| **Dane prywatne** | zadanie zawiera hasło, token, klucz API, PESEL, dane osobowe | 🏠 LOCAL (wymuszone!) |
| **Architektura systemu** | projektowanie mikroserwisów, schematu DB dla nowego projektu, decyzja tech-stack | ☁️ ESCALATE |
| **Debugowanie złożone** | błąd trudny do odtworzenia, race condition, memory leak, problem w >3 plikach | ☁️ ESCALATE |
| **Nowe rozwiązania** | algorytm gdzie nie ma gotowego wzorca, nowa integracja API bez dokumentacji | ☁️ ESCALATE |
| **Wysoka stawka** | kod produkcyjny na live, migracja bazy danych z danymi, zmiana w CI/CD | ☁️ ESCALATE |
| **Wieloplikowy refaktor** | przepisanie modułu >500 linii, zmiana interfejsów publicznych, breaking changes | ☁️ ESCALATE |
| **Analiza i strategia** | ocena ryzyka, planowanie roadmapy, code review całego PR, propozycja architektury | ☁️ ESCALATE |
| **Zadania długie** | zadanie >800 znaków lub >4 kroki planera | ☁️ ESCALATE (preferowane) |
| **Po 2+ failach verifier** | dowolne zadanie, które lokalnie zawiodło ≥2 razy | ☁️ ESCALATE (auto) |

---

## Sygnały językowe

### Słowa → LOCAL
`prosty`, `szybki`, `jednolinijkowy`, `print`, `konwersja`, `parser`, `CRUD`,
`test`, `fixture`, `config`, `template`, `szablon`, `rename`, `zmień nazwę`,
`dodaj komentarz`, `docstring`, `skrypt bash`, `one-liner`, `przelicz`

### Słowa → ESCALATE
`architektura`, `system`, `refaktor całego`, `debuguj`, `race condition`,
`produkcja`, `migracja`, `integracja`, `skomplikowany`, `optymalizuj`,
`wielowątkowy`, `async`, `deployment`, `zaprojektuj`, `oceń`, `przeanalizuj całość`

### Słowa → LOCAL (wymuszone — privacy)
`hasło`, `password`, `token`, `secret`, `api_key`, `klucz api`, `PESEL`,
`prywatny`, `credential`, `bearer`, `authorization`, `private key`, `ssh key`

---

## Wzory użycia w kodzie

```python
from manager.triage import classify_task

decision = classify_task("napisz parser CSV dla pliku z nagłówkami")
# → "local"

decision = classify_task("zaprojektuj architekturę mikroserwisów dla e-commerce")
# → "escalate"

decision, reason = classify_task("zadanie", return_reason=True)
# → ("local", "Prosta operacja mechaniczna — brak słów wysokiej złożoności")
```

---

## Integracja z daemonem

Daemon (`daemon.py`) przy trybie `auto` wywołuje `HybridRouter` — który implementuje
te same reguły programowo (pliki `router/config.yaml` + `router/router.py`).

`classify_task()` w `triage.py` jest **lekkim wrapperem** na router — używaj go gdy
chcesz szybkiej klasyfikacji bez pełnego inicjowania backendu (np. w testach, CLI preview).

---

## Aktualizacja reguł

Progi złożoności (score ≥ 6 → cloud) edytuj w `router/config.yaml`:
- `complexity_score_cloud` — próg złożoności dla eskalacji
- `verifier_fails_escalate` — ile failów verifier przed eskalacją
- `high_complexity_keywords` — lista słów zwiększających złożoność
- `low_complexity_keywords` — lista słów zmniejszających złożoność
