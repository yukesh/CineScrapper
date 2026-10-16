import logging

_logger = None


class LoggingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        no_style = '\033[0m'
        bold = '\033[91m'
        yellow = '\033[93m'
        red = '\033[31m'
        blue_light = '\033[94m'
        grey = '\033[90m'
        start_style = {
            'DEBUG': grey,
            'INFO': blue_light,
            'WARNING': yellow,
            'ERROR': red,
            'CRITICAL': red + bold,
        }.get(record.levelname, no_style)
        return f'{start_style}{super().format(record)}{no_style}'


def setup_logger(level: str = "INFO") -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = logging.getLogger("CineScrapper")
        _logger.handlers.clear()
        handler = logging.StreamHandler()
        handler.setFormatter(LoggingFormatter('{asctime} | {levelname:<8s} | {name:<20s} | {message}', style='{'))
        _logger.addHandler(handler)
    _logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    return _logger


def get_logger() -> logging.Logger:
    if _logger is None:
        setup_logger("DEBUG")
    return _logger
