# Скрипт для скачивание репозиториев с GitHub

from enum import Enum
import subprocess
import argparse
import requests
import sys, os

class Constants(Enum):
    """
    Константы уровня приложения
    """

    REPOS_DIR = "./repos"   # Папка куда будут скачиваться репозитории (создастся сама если ее нет)

class App:
    """Основной класс приложения"""

    @classmethod
    def main(cls):
        
        parser = argparse.ArgumentParser(description='GitHub repositories loader')
        parser.add_argument('--token', 
                            help='GitHub token with access to all repositories',
                            required=True) # обязательно указать токен
        group = parser.add_mutually_exclusive_group(required=True) # либо --all, либо --repos
        group.add_argument('--repos',
                         nargs='+',
                         help='List of repository names to download')
        group.add_argument('--all',
                         action="store_true",
                         help='Download all repositories')
        args = parser.parse_args()

        gd = Downloader(
            args.token, 
            Constants.REPOS_DIR.value,)

        try:
            if args.all:
                gd.download_all_repos()
            elif args.repos:
                for repo in args.repos:
                    gd.download_repo_by_name(repo)
        except Exception as e:
            print(f"downloading error: {e}")
            sys.exit(1)

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

    def download_all_repos(self) -> None:
        """
        **Скачивает все репозитории**

        Если уже есть репо, то обновляет его
        """

        repos = self._get_repos_info()

        for repo in repos:
            self._download_repo(repo)

    def download_repo_by_name(self, repo_name: str) -> None:
        """
        **Скачивает репозиторий по его имени**

        Если уже есть репо, то обновляет его
        """

        repos = self._get_repos_info()

        for r in repos:
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

# color output

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

# end 

if __name__ == "__main__":
    App.main()