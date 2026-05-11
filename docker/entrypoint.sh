#!/bin/sh
set -eu

APP_USER="dsa"
APP_GROUP="dsa"
APP_UID="1000"
APP_GID="1000"
WRITABLE_DIRS="/app/data /app/logs /app/reports"

warn() {
    printf '%s\n' "$*" >&2
}

if [ "$(id -u)" = "0" ]; then
    for dir in $WRITABLE_DIRS; do
        if ! mkdir -p "$dir"; then
            warn "WARN: unable to create $dir; application writes may fail for this path."
            continue
        fi

        owner="$(stat -c '%u:%g' "$dir" 2>/dev/null || true)"
        if [ "$owner" != "$APP_UID:$APP_GID" ]; then
            if ! chown -R "$APP_UID:$APP_GID" "$dir"; then
                warn "WARN: unable to set ownership for $dir; check read-only, rootless, or NFS mount permissions if writes fail."
            fi
        fi

        if ! chmod -R u+rwX "$dir"; then
            warn "WARN: unable to make $dir writable for $APP_USER; check read-only, rootless, or NFS mount permissions if writes fail."
        fi
    done

    exec gosu "$APP_USER:$APP_GROUP" "$@"
fi

exec "$@"
