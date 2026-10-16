# Backup and restore image: pg_dump, restic and rclone around one script.
# Keep postgresql18-client at the server's major version, or pg_dump refuses
# the server.
FROM alpine:3.24

RUN apk add --no-cache postgresql18-client restic rclone \
 && adduser -D -u 10001 backup \
 && install -d -o backup /backup

COPY deploy/backup/tsdhn-backup /usr/local/bin/tsdhn-backup

USER backup
WORKDIR /backup
ENTRYPOINT ["tsdhn-backup"]
CMD ["schedule"]
