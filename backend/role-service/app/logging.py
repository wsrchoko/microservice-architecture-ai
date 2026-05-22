import json, logging, sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
class JSONFormatter(logging.Formatter):
    def format(self, record):
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "role-service", "level": record.levelname, "message": record.getMessage(), "module": record.module, "function": record.funcName, "line": record.lineno}
        if hasattr(record, "extra_fields"): entry.update(record.extra_fields)
        if record.exc_info and record.exc_info[0]: entry["exception"] = {"type": record.exc_info[0].__name__, "message": str(record.exc_info[1])}
        return json.dumps(entry, default=str)
def setup_logging(service_name="role-service", log_level="INFO", json_format=True):
    logger = logging.getLogger(); logger.setLevel(getattr(logging, log_level.upper(), logging.INFO)); logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter() if json_format else logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs): extra = kwargs.get("extra", {}); extra.update(self.extra or {}); kwargs["extra"] = extra; return msg, kwargs
def get_logger(name, **kwargs): return LoggerAdapter(logging.getLogger(name))