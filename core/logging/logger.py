import logging
from pathlib import Path

def get_logger(name="moex_ai"):
    Path("logs").mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    logger.addHandler(stream)
    file = logging.FileHandler("logs/moex_ai.log", encoding="utf-8")
    file.setFormatter(fmt)
    logger.addHandler(file)
    return logger
