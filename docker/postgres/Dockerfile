FROM postgres:17.6
COPY docker/postgres/init-services.sh /docker-entrypoint-initdb.d/10-init-services.sh
COPY --chmod=0755 docker/postgres/bootstrap-role.sh /usr/local/bin/bootstrap-role.sh
