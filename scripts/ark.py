# Скрипт для бэкапов (ark от англ. - ковчег)

from typing import Callable
from types import FrameType
from enum import Enum
import argparse
import signal
import sys
import os

class App:
    """Основной класс приложения"""

    @classmethod
    def _args_parse(cls) -> argparse.Namespace:
        parser = argparse.ArgumentParser()

        script_name = os.path.basename(__file__)
        
        usage = \
f"""
ark - hard drive backuper

Usage examples:
    Backup files/folders (src) to multiple destinations:
        {script_name} --src src1 src2 ... --dst dst1 dst2 ...
"""

        def custom_print_help():
            ColorPrinter.blue(usage)

        def custom_error(message):
            custom_print_help()
            ColorPrinter.red(f"{message}")
            sys.exit(1)

        parser.print_help = custom_print_help
        parser.error = custom_error

        parser.add_argument('--src', nargs='+', required=True)
        parser.add_argument('--dst', nargs='+', required=True)
        return parser.parse_args()

    @classmethod
    def main(cls) -> None:
        def on_exit():
            ColorPrinter.red("\nhandle exit signal")
            sys.exit(1)

        SignalHandler(on_exit)
        args = cls._args_parse()
        try:
            for src in args.src:
                print(src)
            for dst in args.dst:
                print(dst)
        except Exception as e:
            ColorPrinter.red(f"backuping error: {str(e).rstrip()}")
        finally:
            ColorPrinter.blue("\nsee you later!")

class Backup:
    pass

# tools

class SignalHandler:

    def __init__(self, on_exit: Callable) -> None:
        self._on_exit = on_exit
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)

        self._hide_control_chars()
        self._setup_signal_handlers()

    def restore_original_handlers(self) -> None:
        """Восстанавливает оригинальные обработчики сигналов"""

        signal.signal(signal.SIGINT, self._original_sigint)
        signal.signal(signal.SIGTERM, self._original_sigterm)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del exc_type, exc_val, exc_tb
        self.restore_original_handlers()

    def _setup_signal_handlers(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _hide_control_chars(self) -> None:
        if not sys.stdin.isatty():
            return
        if sys.platform != "win32":
            try:
                import termios
                fd = sys.stdin.fileno()
                attrs = termios.tcgetattr(fd)
                attrs[3] &= ~termios.ECHOCTL
                termios.tcsetattr(fd, termios.TCSANOW, attrs)
            except Exception as e:
                raise RuntimeError("error while configuring terminal") from e

    def _handle_signal(self, signum: int, frame: FrameType) -> None:
        del signum, frame
        self._on_exit()

class ConsoleColors(Enum):
    RED = '\033[1;31m'
    GREEN = '\033[1;32m'
    BLUE = '\033[1;34m'
    RESET = '\033[0m'

class ColorPrinter:
    """Цветной вывод в консоль"""

    @classmethod
    def red(cls, message: str = "") -> None:
        cls._color_print(message, ConsoleColors.RED.value)

    @classmethod
    def green(cls, message: str = "") -> None:
        cls._color_print(message, ConsoleColors.GREEN.value)

    @classmethod
    def blue(cls, message: str = "") -> None:
        cls._color_print(message, ConsoleColors.BLUE.value)

    @classmethod
    def _color_print(cls, message: str, color_code: str) -> None:
        """Вывод сообщения _message_ в цвете _color_code_"""

        try:
            cls._enable_windows_ansi()
            print(f"{color_code}{message}{ConsoleColors.RESET.value}")
        except Exception:
            print(message)

    @classmethod
    def _enable_windows_ansi(cls) -> None:
        """Включает поддержку ANSI escape sequences в Windows консоли"""

        if sys.platform == "win32":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                hStdOut = kernel32.GetStdHandle(-11)
                mode = ctypes.c_ulong()
                kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode))
                mode.value |= 0x0004
                kernel32.SetConsoleMode(hStdOut, mode)
            except Exception as e:
                raise RuntimeError("failed to enable ANSI colors") from e

# end

if __name__ == "__main__":
    App.main()