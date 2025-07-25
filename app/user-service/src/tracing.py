"""
OpenTelemetry трейсинг для User Service
"""
import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

def setup_tracing(app):
    """
    Настройка OpenTelemetry трейсинга для User Service
    """
    try:
        # Получаем конфигурацию из переменных окружения
        service_name = os.environ.get("OTEL_SERVICE_NAME", "user-service")
        jaeger_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318/v1/traces")
        
        logger.info(f"Setting up tracing for service: {service_name}")
        logger.info(f"Jaeger endpoint: {jaeger_endpoint}")
        
        # Создаем ресурс с информацией о сервисе
        resource = Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": "development"
        })
        
        # Настраиваем TracerProvider
        trace.set_tracer_provider(TracerProvider(resource=resource))
        tracer_provider = trace.get_tracer_provider()
        
        # Настраиваем экспортер для Jaeger через OTLP
        # Исправляем ошибку: убираем параметр insecure, который не поддерживается в новых версиях
        otlp_exporter = OTLPSpanExporter(
            endpoint=jaeger_endpoint
        )
        
        # Добавляем batch processor для эффективной отправки spans
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)
        
        # Автоматическая инструментация FastAPI
        FastAPIInstrumentor.instrument_app(app)
        
        # Автоматическая инструментация HTTPX для межсервисных вызовов
        HTTPXClientInstrumentor().instrument()
        
        logger.info("OpenTelemetry tracing setup completed successfully")
        
        # Возвращаем tracer для использования в приложении
        return trace.get_tracer(__name__)
        
    except Exception as e:
        logger.error(f"Failed to setup tracing: {e}")
        # Возвращаем no-op tracer в случае ошибки
        return trace.NoOpTracer()

def get_tracer():
    """
    Получить tracer для создания custom spans
    """
    return trace.get_tracer(__name__)
