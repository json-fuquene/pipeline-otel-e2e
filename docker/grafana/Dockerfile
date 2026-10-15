FROM grafana/grafana:12.2.0

COPY --chown=472:0 docker/grafana/provisioning/ /etc/grafana/provisioning/
COPY --chown=472:0 docker/grafana/dashboards/ /var/lib/grafana/dashboards/
