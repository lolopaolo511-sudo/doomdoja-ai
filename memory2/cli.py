#!/usr/bin/env python3
"""
memory2 CLI — zarządzaj 3-wymiarową pamięcią agenta.

Użycie:
  python3 memory2/cli.py remember semantic "Python dict O(1)"
  python3 memory2/cli.py remember episodic "Zadanie X ukończone" --outcome success
  python3 memory2/cli.py remember procedural "Jak scrapować" --name scrape --steps "find" "parse"
  python3 memory2/cli.py recall "szybkość dict"
  python3 memory2/cli.py recall "scraping" --type procedural
  python3 memory2/cli.py forget semantic 42
  python3 memory2/cli.py status
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from memory2.memory2 import Memory2


def main() -> int:
    parser = argparse.ArgumentParser(description="Memory2 CLI")
    sub = parser.add_subparsers(dest="cmd")

    # remember
    p_rem = sub.add_parser("remember", help="Zapisz wspomnienie")
    p_rem.add_argument("type", choices=["semantic", "episodic", "procedural"])
    p_rem.add_argument("content")
    p_rem.add_argument("--tags", nargs="*", default=[])
    p_rem.add_argument("--outcome", default="", help="[episodic/procedural] success|fail|error")
    p_rem.add_argument("--task-id", default="", help="[episodic] ID zadania")
    p_rem.add_argument("--name", default="", help="[procedural] Nazwa procedury")
    p_rem.add_argument("--steps", nargs="*", default=[], help="[procedural] Kroki")

    # recall
    p_rec = sub.add_parser("recall", help="Przypomnij wspomnienia")
    p_rec.add_argument("query")
    p_rec.add_argument("--type", default=None,
                       choices=["semantic", "episodic", "procedural"])
    p_rec.add_argument("--top-k", type=int, default=5)
    p_rec.add_argument("--tags", nargs="*", default=[])
    p_rec.add_argument("--context", action="store_true",
                       help="Wyświetl jako blok kontekstu (do wklejenia w prompt)")

    # forget
    p_forget = sub.add_parser("forget", help="Usuń wspomnienie")
    p_forget.add_argument("type", choices=["semantic", "episodic", "procedural"])
    p_forget.add_argument("id", type=int)

    # status
    sub.add_parser("status", help="Pokaż statystyki pamięci")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 1

    mem = Memory2()

    if args.cmd == "remember":
        meta = {}
        if args.outcome:
            meta["outcome"] = args.outcome
        if args.task_id:
            meta["task_id"] = args.task_id
        if args.name:
            meta["name"] = args.name
        if args.steps:
            meta["steps"] = args.steps
        mid = mem.remember(args.type, args.content, tags=args.tags or None,
                           meta=meta or None)
        print(f"[{args.type.upper()}] Zapisano id={mid}: {args.content[:80]}")

    elif args.cmd == "recall":
        if args.context:
            ctx = mem.recall_context(args.query, top_k=args.top_k)
            print(ctx or "(brak pasujących wspomnień)")
            return 0
        results = mem.recall(args.query, type=args.type, top_k=args.top_k,
                             tags=args.tags or None)
        if not results:
            print("Brak pasujących wspomnień.")
            return 0
        for r in results:
            mt = r.get("memory_type", args.type or "?")
            score = r.get("score", 0)
            ts = r.get("created_at", r.get("updated_at", "?"))[:16].replace("T", " ")
            tags_str = f" [{', '.join(r['tags'])}]" if r.get("tags") else ""
            print(f"[{mt.upper()}] id={r['id']} score={score:.2f} {ts}{tags_str}")
            print(f"    {r['content'][:120]}")
            if r.get("steps"):
                print(f"    kroki: {r['steps']}")

    elif args.cmd == "forget":
        ok = mem.forget(args.type, args.id)
        print(f"Usunięto [{args.type}] id={args.id}" if ok else "Nie znaleziono.")

    elif args.cmd == "status":
        s = mem.status()
        print(f"Backend semantyczny : {s['semantic_backend']}")
        print(f"Epizodyczne łącznie : {s['episodic_total']}")
        print(f"Wyniki epizodów     : {s['episodic_outcomes']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
