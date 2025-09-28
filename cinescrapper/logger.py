import logging

_logger = None  # private global


class LoggingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord):
        no_style = '\033[0m'
        bold = '\033[91m'
        yellow = '\033[93m'
        red = '\033[31m'
        blue_light = '\033[94m'
        purple = '\033[35m'
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
    """Configure the global logger (should be called once in __main__.py)."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger("CineScrapper")
        _logger.handlers.clear()

        handler = logging.StreamHandler()
        formatter = LoggingFormatter(
            '{asctime} | {levelname:<8s} | {name:<20s} | {message}',
            style='{'
        )
        handler.setFormatter(formatter)
        _logger.addHandler(handler)

    # Always update level when setup_logger is called
    _logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    return _logger


def get_logger() -> logging.Logger:
    """Get the already-configured logger."""
    if _logger is None:
        # Auto-init with default INFO level
        setup_logger("DEBUG")
    return _logger
