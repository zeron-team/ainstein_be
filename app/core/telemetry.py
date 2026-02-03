# app/core/telemetry.py
"""
FERRO D2 v3.0.0 - OpenTelemetry Integration

Provides end-to-end observability:
- Distributed tracing with spans
- Metrics collection
- FastAPI auto-instrumentation
- Database and Redis instrumentation

FERRO D2 Required Spans:
- http.server: HTTP request handling
- auth.validate: Authentication/authorization
- cache.lookup/store: Redis operations
- retrieval.qdrant.search: Vector search
- llm.generate: LLM generation
- tool.{name}: Tool executions
"""

from __future__ import annotations

import logging
from typing import Optional
from functools import wraps

from app.core.config import settings

log = logging.getLogger(__name__)

# Global tracer instance
_tracer = None
_meter = None
_initialized = False


def init_telemetry(service_name: str = "ainstein-api"):
    """
    Initialize OpenTelemetry with OTLP exporter.
    
    Should be called once at application startup.
    """
    global _tracer, _meter, _initialized
    
    if _initialized:
        return
    
    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        
        # Check if OTLP endpoint is configured
        otlp_endpoint = getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", None)
        
        # Create resource with service name
        resource = Resource(attributes={
            SERVICE_NAME: service_name,
            "service.version": "3.0.0",
            "deployment.environment": getattr(settings, "ENV", "dev"),
        })
        
        # Initialize tracer provider
        tracer_provider = TracerProvider(resource=resource)
        
        # Add OTLP exporter if endpoint configured
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
                
                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                
                # Metrics
                metric_reader = PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=otlp_endpoint),
                    export_interval_millis=30000,
                )
                meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
                metrics.set_meter_provider(meter_provider)
                _meter = metrics.get_meter(__name__)
                
                log.info("[Telemetry] OTLP exporter configured: %s", otlp_endpoint)
            except Exception as e:
                log.warning("[Telemetry] Failed to configure OTLP exporter: %s", e)
        
        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)
        _tracer = trace.get_tracer(__name__)
        _initialized = True
        
        log.info("[Telemetry] OpenTelemetry initialized for service: %s", service_name)
        
    except ImportError:
        log.warning("[Telemetry] OpenTelemetry packages not installed")
    except Exception as e:
        log.warning("[Telemetry] Failed to initialize: %s", e)


def get_tracer():
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        init_telemetry()
    return _tracer


def get_meter():
    """Get the global meter instance."""
    global _meter
    return _meter


def instrument_fastapi(app):
    """
    Instrument FastAPI application with OpenTelemetry.
    
    Call this after creating the FastAPI app.
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        
        FastAPIInstrumentor.instrument_app(app)
        log.info("[Telemetry] FastAPI instrumented")
    except ImportError:
        log.warning("[Telemetry] FastAPI instrumentation not available")
    except Exception as e:
        log.warning("[Telemetry] Failed to instrument FastAPI: %s", e)


def instrument_sqlalchemy(engine):
    """Instrument SQLAlchemy engine."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        
        SQLAlchemyInstrumentor().instrument(engine=engine)
        log.info("[Telemetry] SQLAlchemy instrumented")
    except ImportError:
        log.warning("[Telemetry] SQLAlchemy instrumentation not available")
    except Exception as e:
        log.warning("[Telemetry] Failed to instrument SQLAlchemy: %s", e)


def instrument_redis(client):
    """Instrument Redis client."""
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        
        RedisInstrumentor().instrument()
        log.info("[Telemetry] Redis instrumented")
    except ImportError:
        log.warning("[Telemetry] Redis instrumentation not available")
    except Exception as e:
        log.warning("[Telemetry] Failed to instrument Redis: %s", e)


# ============================================================================
# Span Decorators
# ============================================================================

def traced(span_name: str, attributes: Optional[dict] = None):
    """
    Decorator to add tracing to a function.
    
    Usage:
        @traced("llm.generate")
        async def generate_response(prompt: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            if tracer is None:
                return await func(*args, **kwargs)
            
            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error", str(e))
                    span.record_exception(e)
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            if tracer is None:
                return func(*args, **kwargs)
            
            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error", str(e))
                    span.record_exception(e)
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# ============================================================================
# Metrics
# ============================================================================

class Metrics:
    """FERRO D2 required metrics."""
    
    _request_duration = None
    _cache_hit_ratio = None
    _llm_duration = None
    _errors_total = None
    
    @classmethod
    def init(cls):
        """Initialize metrics."""
        meter = get_meter()
        if meter is None:
            return
        
        cls._request_duration = meter.create_histogram(
            name="request_duration_ms",
            description="Request duration in milliseconds",
            unit="ms",
        )
        
        cls._cache_hit_ratio = meter.create_counter(
            name="cache_hits_total",
            description="Total cache hits",
        )
        
        cls._llm_duration = meter.create_histogram(
            name="llm_generate_ms",
            description="LLM generation duration in milliseconds",
            unit="ms",
        )
        
        cls._errors_total = meter.create_counter(
            name="errors_total",
            description="Total errors by type",
        )
    
    @classmethod
    def record_request_duration(cls, duration_ms: float, attributes: dict = None):
        if cls._request_duration:
            cls._request_duration.record(duration_ms, attributes or {})
    
    @classmethod
    def record_cache_hit(cls, hit: bool, attributes: dict = None):
        if cls._cache_hit_ratio:
            cls._cache_hit_ratio.add(1 if hit else 0, attributes or {})
    
    @classmethod
    def record_llm_duration(cls, duration_ms: float, attributes: dict = None):
        if cls._llm_duration:
            cls._llm_duration.record(duration_ms, attributes or {})
    
    @classmethod
    def record_error(cls, error_type: str, attributes: dict = None):
        if cls._errors_total:
            attrs = {"error_type": error_type}
            attrs.update(attributes or {})
            cls._errors_total.add(1, attrs)
