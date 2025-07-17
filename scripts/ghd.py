# Скрипт для скачивание репозиториев с GitHub (ghd = github downloader)

from types import FrameType
from typing import Callable
from enum import Enum
import subprocess
import argparse
import requests
import signal
import sys
import os

class Constants(Enum):
    """
    Константы уровня приложения
    """

    REPOS_DIR = "./repos" # Папка куда будут скачиваться репозитории (создастся сама если ее нет)

class App:
    """Основной класс приложения"""

    @classmethod
    def _args_parse(cls) -> argparse.Namespace:
        parser = argparse.ArgumentParser()

        script_name = os.path.basename(__file__)

        usage = \
f"""
GitHub Repositories Downloader

Usage examples:
    Download specific repositories:
        {script_name} --token YOUR_TOKEN --repos repo1 repo2

    Download all repositories:
        {script_name} --token YOUR_TOKEN --all
"""

        def custom_print_help():
            ColorPrinter.blue(usage)

        def custom_error(message):
                custom_print_help()
                ColorPrinter.red(f"{message}")
                sys.exit(1)

        parser.print_help = custom_print_help
        parser.error = custom_error
        parser.add_argument('--token', required=True) # обязательно указать токен
        group = parser.add_mutually_exclusive_group(required=True) # либо --all, либо --repos
        group.add_argument('--repos', nargs='+')
        group.add_argument('--all', action="store_true")
        return parser.parse_args()

    @classmethod
    def main(cls) -> None:
        
        def on_exit():
            ColorPrinter.red("\nhandle exit signal")
            sys.exit(1)

        SignalHandler(on_exit)
        args = cls._args_parse()

        loader = Downloader(
            args.token, 
            Constants.REPOS_DIR.value,)

        try:
            if args.all:
                loader.download_all_repos()
            elif args.repos:
                for repo in args.repos:
                    loader.download_repo_by_name(repo)
        except Exception as e:
            ColorPrinter.red(f"downloading error: {str(e).rstrip()}")
        finally:
            ColorPrinter.blue("\nsee you later!")

# downloader

class Downloader:
    """
    Управляет загрузкой репозиториев с GitHub
    """

    def __init__(self, token: str, target_dir: str) -> None:
        """
        Принимает токен GitHub
        
        Для корректной работы необходимо чтобы токен имел доступ ко всем репозиториям
        """

        self.token = token
        self.target_dir = target_dir

        self.base_url = "https://github.com"
        self.api_url = "https://api.github.com"
        self.api_headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

        self.repos = self._get_repos_info()

    def download_all_repos(self) -> None:
        """
        **Скачивает все репозитории**

        Если уже есть репо, то обновляет его
        """

        for repo in self.repos:
            self._download_repo(repo)

    def download_repo_by_name(self, repo_name: str) -> None:
        """
        **Скачивает репозиторий по его имени**

        Если уже есть репо, то обновляет его
        """

        for r in self.repos:
            if r["name"] == repo_name:
                self._download_repo(r)
                return

        raise RuntimeError(f"repo '{repo_name}' not found")

    def _download_repo(self, repo: dict) -> None:
        """
        **Скачивание репозитория**

        Принимает словарь с информацией о репо, который возвращает GitHub API
        """

        if not os.path.exists(self.target_dir):
            os.makedirs(self.target_dir, exist_ok=True)

        repo_name = repo["name"]
        clone_url = repo["clone_url"].replace(
            "https://",
            f"https://{self.token}@"
        )
        repo_path = os.path.join(self.target_dir, repo_name)
        
        try:
            ColorPrinter.blue(f"downloading '{repo_name}' from github...")
            if os.path.exists(repo_path):
                subprocess.run(
                    ["git", "-C", repo_path, "reset", "--hard"],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                subprocess.run(
                    ["git", "-C", repo_path, "pull"],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            else:
                subprocess.run(
                    ["git", "clone", clone_url, repo_path],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            ColorPrinter.blue(f"downloaded '{repo_name}' from github")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"git command failed: {e}") from e

    def _get_repos_info(self) -> list[dict]:
        """
        **Получает информацию обо всех репозиториях**

        В случае если статус-код ответа не 200 инициирует RuntimeError
        """

        page, repos = 1, []
        
        while True:
            response = requests.get(
                f"{self.api_url}/user/repos",
                headers=self.api_headers,
                params={"page": page, "per_page": 100}
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"failed to get repos: {response.text}")
            
            items = response.json()
            if not items:
                break
                
            repos.extend(items)
            page += 1
        
        return repos

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
                raise RuntimeError("failed to enable ANSI colors") from e

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

# end 

if __name__ == "__main__":
    App.main()