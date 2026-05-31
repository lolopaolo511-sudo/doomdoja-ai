#!/usr/bin/env python3
"""
CLI do zarządzania pamięcią agenta.
Użycie:
  python3 memory_cli.py remember "fakt do zapamiętania"
  python3 memory_cli.py recall "pytanie"
  python3 memory_cli.py list
  python3 memory_cli.py stats
  python3 memory_cli.py forget <id>
"""

import argparse
import sys
from memory import AgentMemory


def main():
    parser = argparse.ArgumentParser(description="Pamięć agenta CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_rem = sub.add_parser("remember", help="Zapamiętaj fakt")
    p_rem.add_argument("content", help="Treść faktu")
    p_rem.add_argument("--tags", nargs="*", default=[], help="Tagi")
    p_rem.add_argument("--session", default="cli", help="ID sesji")
    p_rem.add_argument("--importance", type=int, default=1, help="Ważność 1-5")

    p_rec = sub.add_parser("recall", help="Przypomnij podobne fakty")
    p_rec.add_argument("query", help="Zapytanie")
    p_rec.add_argument("--top-k", type=int, default=5)
    p_rec.add_argument("--tags", nargs="*", default=[])

    sub.add_parser("list", help="Pokaż ostatnie wspomnienia")
    sub.add_parser("stats", help="Statystyki pamięci")

    p_forget = sub.add_parser("forget", help="Usuń wspomnienie")
    p_forget.add_argument("id", type=int, help="ID wspomnienia")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    mem = AgentMemory()

    if args.cmd == "remember":
        mid = mem.remember(args.content, tags=args.tags, session_id=args.session,
                           importance=args.importance)
        print(f"Zapisano [id={mid}]: {args.content[:80]}")

    elif args.cmd == "recall":
        results = mem.recall(args.query, top_k=args.top_k, tags=args.tags or None)
        if not results:
            print("Brak pasujących wspomnień.")
        for r in results:
            dist = r["distance"]
            ts = r["created_at"][:16].replace("T", " ")
            tags_str = f" [{', '.join(r['tags'])}]" if r["tags"] else ""
            print(f"[{r['id']}] dist={dist:.3f} | {ts}{tags_str}")
            print(f"    {r['content']}")

    elif args.cmd == "list":
        items = mem.recall_all(50)
        if not items:
            print("Pamięć pusta.")
        for r in items:
            ts = r["created_at"][:16].replace("T", " ")
            tags_str = f" [{', '.join(r['tags'])}]" if r["tags"] else ""
            print(f"[{r['id']}] {ts}{tags_str} | {r['content'][:100]}")

    elif args.cmd == "stats":
        s = mem.stats()
        print(f"Łącznie wspomnień : {s['total']}")
        print(f"Najstarsze        : {s['oldest']}")
        print(f"Najnowsze         : {s['newest']}")
        print(f"Baza danych       : {s['db']}")

    elif args.cmd == "forget":
        mem.forget(args.id)
        print(f"Usunięto wspomnienie id={args.id}")

    mem.close()


if __name__ == "__main__":
    main()
