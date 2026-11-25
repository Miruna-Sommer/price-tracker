#!/bin/bash
# Verificare programată (cron / Task Scheduler): verifică prețurile,
# păstrează jurnalul și regenerează CSV-ul și graficele din date/.
cd "$(dirname "$0")/.."
DB=date/prices.db
mkdir -p date/grafice
{ echo "=== $(date '+%Y-%m-%d %H:%M') ==="; python tracker.py --db "$DB" check 2>&1; echo; } | tee -a date/check_log.txt
python tracker.py --db "$DB" export --out date/istoric.csv
for id in $(python -c "import db; print(' '.join(str(p['id']) for p in db.list_products(db.connect('$DB'))))"); do
  python tracker.py --db "$DB" plot "$id" --out "date/grafice/grafic_$id.png" > /dev/null
done
