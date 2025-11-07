import json
import logging
import traceback


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "func": record.funcName,
            "event": record.msg,
        }
        
        return json.dumps(log_record)
