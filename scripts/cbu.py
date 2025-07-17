# Скрипт для загрузки репозиториев на CodeBerg (cbu = codeberg uploader)

from types import FrameType
from typing import Callable
from enum import Enum
import argparse
import signal
import sys

class Constants(Enum):
    """
    Константы уровня приложения
    """

    REPOS_DIR = "./repos" # Папка с репозиториями

class App:
    """Основной класс приложения"""

    @classmethod
    def _args_parse(cls) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description='codeberg repositories uploader')

        def custom_error(message):
                ColorPrinter.blue(parser.format_help())
                ColorPrinter.red(f"{message}")
                sys.exit(1)

        def custom_print_help():
            ColorPrinter.blue(parser.format_help())

        parser.print_help = custom_print_help
        parser.error = custom_error
        parser.add_argument('--token', 
                            help='codeberg token with access to all repositories',
                            required=True) # обязательно указать токен
        group = parser.add_mutually_exclusive_group(required=True) # либо --all, либо --repos
        group.add_argument('--repos',
                         nargs='+',
                         help='list of repository names to upload')
        group.add_argument('--all',
                         action="store_true",
                         help='upload all repositories')
        return parser.parse_args()
    
    @classmethod
    def main(cls) -> None:
        def on_exit():
            ColorPrinter.red("\nhandle exit signal")
            sys.exit(1)

        SignalHandler(on_exit)
        args = cls._args_parse()

        try:
            if args.all:
                print("all")
            elif args.repos:
                print("repos")
        except Exception as e:
            ColorPrinter.red(f"uploading error: {e}")
        finally:
            ColorPrinter.blue("\nsee you later!")

# recipes

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
                raise RuntimeError("Failed to enable ANSI colors") from e

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

    # Код с __enter__ и __exit__ позволяет использовать класс SignalHandler в конструкции with,
    # что автоматически восстанавливает оригинальные обработчики сигналов при выходе из блока.
    # with SignalHandler(cleanup):  # Вызывается __enter__
    # Основной код программы
    # print("Работаю...")
    # При выходе из блока автоматически вызовется __exit__ и restore_original_handlers()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore_original_handlers()

    def _setup_signal_handlers(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _hide_control_chars(self) -> None:
        try:
            # Если терминала нет - выход (например если скрипт запустился на сервере)
            if not sys.stdin.isatty():
                return
            if sys.platform != "win32":
                import termios
                fd = sys.stdin.fileno()
                # termios.tcgetattr(fd) считывает текущие атрибуты терминала в attrs
                attrs = termios.tcgetattr(fd)
                # attrs[3] соответствует локальным флагам (c_lflag в структуре termios)
                # ECHOCTL — это флаг, который управляет отображением управляющих символов (например, ^C для Ctrl+C).
                # ~termios.ECHOCTL инвертирует битовую маску, а &= применяет побитовое И, чтобы сбросить этот флаг
                attrs[3] &= ~termios.ECHOCTL
                termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except:
            pass

    def _handle_signal(self, signum: int, frame: FrameType) -> None:
        del signum, frame
        self._on_exit()

# end 

if __name__ == "__main__":
    App.main()