#!/bin/bash
# Dodaj zadanie do kolejki agenta
# Użycie:
#   ./add-task.sh "Napisz funkcję X w pliku Y"         # treść jako argument
#   ./add-task.sh < zadanie.txt                         # treść z pliku

TASKS_PENDING="$(dirname "$0")/tasks/pending"

# Generuj unikalną nazwę pliku (timestamp)
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
NEXT_NUM=$(ls "$TASKS_PENDING"/*.txt 2>/dev/null | wc -l | tr -d ' ')
NEXT_NUM=$((NEXT_NUM + 1))
FILENAME="${TASKS_PENDING}/$(printf '%03d' $NEXT_NUM)_task_${TIMESTAMP}.txt"

if [[ -n "$1" ]]; then
    echo "$1" > "$FILENAME"
else
    cat > "$FILENAME"
fi

echo "Zadanie dodane: $FILENAME"
echo "Zawartość:"
cat "$FILENAME"
echo ""
echo "Uruchom agenta: python3 $(dirname "$0")/agent_runner.py --repo /twoje/repo"
