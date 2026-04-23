FROM edoburu/pgbouncer:latest

USER root

RUN apk add --no-cache aws-cli jq gettext

COPY pgbouncer.ini.template /etc/pgbouncer/pgbouncer.ini.template
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

USER postgres

ENTRYPOINT ["/entrypoint.sh"]