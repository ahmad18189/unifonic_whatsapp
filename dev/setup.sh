#!/usr/bin/env bash
# Idempotent Frappe v15 bench setup inside the dev "bench" container, with this app linked live.
#   docker compose -f dev/docker-compose.yml up -d
#   docker compose -f dev/docker-compose.yml exec bench bash /workspace/unifonic_whatsapp/dev/setup.sh
#   docker compose -f dev/docker-compose.yml exec bench bash -lc \
#     'cd ~/frappe-bench && bench --site uw.localhost run-tests --app unifonic_whatsapp'
set -euo pipefail

BENCH=/home/frappe/frappe-bench
SITE=${SITE:-uw.localhost}
APP_SRC=/workspace/unifonic_whatsapp
PYTHON=${PYTHON:-$HOME/.pyenv/versions/3.12.16/bin/python}

cd /home/frappe
# The image's MariaDB client requires TLS by default; the dev server on the private
# compose network has none.
if ! grep -q '^skip-ssl' ~/.my.cnf 2>/dev/null; then
  printf '[client]\nskip-ssl\n' >> ~/.my.cnf
fi
# The bench directory is a mounted volume, so it exists but may be empty.
if [ ! -f "$BENCH/sites/apps.txt" ]; then
  bench init --frappe-branch version-15 --skip-redis-config-generation --python "$PYTHON" \
    --ignore-exist frappe-bench
fi

cd "$BENCH"
bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis:6379
bench set-config -g redis_queue redis://redis:6379
bench set-config -g redis_socketio redis://redis:6379

if [ ! -e apps/unifonic_whatsapp ]; then
  ln -s "$APP_SRC" apps/unifonic_whatsapp
fi
./env/bin/pip install -q -e apps/unifonic_whatsapp
# bench writes apps.txt without a trailing newline; add one before appending.
sed -i 's/^frappeunifonic_whatsapp$/frappe/; $a\' sites/apps.txt
grep -qxF unifonic_whatsapp sites/apps.txt || echo unifonic_whatsapp >> sites/apps.txt

if [ ! -d "sites/$SITE" ]; then
  bench new-site "$SITE" --db-root-username root --db-root-password "$DB_ROOT_PASSWORD" \
    --admin-password admin --mariadb-user-host-login-scope='%'
fi
bench --site "$SITE" list-apps | grep -q unifonic_whatsapp || bench --site "$SITE" install-app unifonic_whatsapp
bench --site "$SITE" set-config allow_tests true
bench --site "$SITE" migrate
bench use "$SITE"
echo "Bench ready: site $SITE"
