FROM locustio/locust

RUN pip install \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-instrumentation-requests \
    opentelemetry-exporter-otlp