from loguru import logger


def setup_logging():
    logger.remove()

    FILE_FORMAT = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(
        "logs/script_logs.log",
        colorize=False,
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format=FILE_FORMAT,
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        colorize=True,
        format="<level>{time:HH:mm:ss} {level: <8} {message}</level>",
    )
