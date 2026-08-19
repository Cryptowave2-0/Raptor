"""Utilities for logging messages to the console with color coding and timestamps."""

from enum import Enum
from datetime import datetime

from colorama import Fore, Style
from discord import Color

from typing import List, Tuple

class LogTypes(str, Enum):
    WARNING = "WARNING"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    EVENT = "EVENT"
    COMMAND = "COMMAND"
    ADMIN_COMMAND = "ADMIN_COMMAND"
    DEBUG = "DEBUG"


LOG_COLORS = {
    LogTypes.WARNING: (Fore.YELLOW, Color.yellow()),
    LogTypes.INTERNAL_ERROR: (Fore.RED, Color.red()),
    LogTypes.EVENT: (Fore.BLUE, Color.blue()),
    LogTypes.COMMAND: (Fore.GREEN, Color.green()),
    LogTypes.ADMIN_COMMAND: (Fore.MAGENTA, Color.magenta()),
    LogTypes.DEBUG: (Fore.WHITE, Color.from_rgb(255, 255, 255)),
}

TYPE_LABEL_WIDTH = 13


class LogManager:
    @staticmethod
    def log(text: str, type_: LogTypes) -> None:
        """Logs a message to the console with a timestamp and color coding based on the log type."""
        if not isinstance(type_, LogTypes):
            LogManager.log(f"'{type_}' is not a valid LogTypes value", LogTypes.INTERNAL_ERROR)
            return

        time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        label = type_.value.ljust(TYPE_LABEL_WIDTH)
        color, _ = LOG_COLORS[type_]

        print(
            f"{Fore.LIGHTBLACK_EX}{Style.BRIGHT}{time_now}{Style.RESET_ALL} "
            f"{color}{Style.BRIGHT}{label}{Style.RESET_ALL}\t{text}"
        )

    @staticmethod
    def logs(list_of_logs: List[Tuple[str, LogTypes]]) -> None:
        """Logs multiple messages from a list of tuples containing the message and its log type."""
        for text, type_ in list_of_logs:
            LogManager.log(text, type_)