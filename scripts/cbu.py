# Скрипт для загрузки репозиториев на CodeBerg (cbu = codeberg uploader)

from types import FrameType
from typing import Callable
from enum import Enum
import subprocess
import requests
import argparse
import signal
import sys
import os

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

        script_name = os.path.basename(__file__)

        usage = \
f"""
CodeBerg Repository Manager

Main commands:
    upload      Upload repositories to CodeBerg
    delete      Delete repositories from CodeBerg

Usage examples:
    Upload specific repositories:
        {script_name} --token YOUR_TOKEN upload --repos repo1 repo2
  
    Upload all repositories:
        {script_name} --token YOUR_TOKEN upload --all
  
    Delete specific repositories:
        {script_name} --token YOUR_TOKEN delete --repos repo1 repo2
  
    Delete all repositories:
        {script_name} --token YOUR_TOKEN delete --all
"""

        def custom_print_help():
            ColorPrinter.blue(usage)

        def custom_error(message):
                custom_print_help()
                ColorPrinter.red(f"{message}")
                sys.exit(1)

        parser.print_help = custom_print_help
        parser.error = custom_error
        parser.add_argument('--token', 
                            help='codeberg token with access to all repositories',
                            required=True) # обязательно указать токен
        
        # Основная группа действий (upload/delete)
        action_subparsers = parser.add_subparsers(dest='action', required=True)
        
        # Парсер для операций загрузки
        upload_parser = action_subparsers.add_parser('upload', 
                                                     help='upload repositories')
        upload_parser.print_help = custom_print_help
        upload_parser.error = custom_error
        upload_group = upload_parser.add_mutually_exclusive_group(required=True)
        upload_group.add_argument('--repos', 
                                  nargs='+', 
                                  help='list of repository names to upload')
        upload_group.add_argument('--all', 
                                  action='store_true', 
                                  help='upload all repositories')
        
        # Парсер для операций удаления
        delete_parser = action_subparsers.add_parser('delete', 
                                                     help='delete repositories')
        delete_parser.print_help = custom_print_help
        delete_parser.error = custom_error
        delete_group = delete_parser.add_mutually_exclusive_group(required=True)
        delete_group.add_argument('--repos', 
                                  nargs='+', 
                                  help='list of repository names to delete')
        delete_group.add_argument('--all', 
                                  action='store_true', 
                                  help='delete all repositories')

        return parser.parse_args()
    
    @classmethod
    def main(cls) -> None:
        def on_exit():
            ColorPrinter.red("\nhandle exit signal")
            sys.exit(1)

        SignalHandler(on_exit)
        args = cls._args_parse()

        try:
            loader = Uploader(
                args.token, 
                Constants.REPOS_DIR.value,)

            if args.action == 'upload':
                if args.all:
                    loader.upload_all_repos()
                elif args.repos:
                    for repo in args.repos:
                        loader.upload_repo_by_name(repo)
            elif args.action == 'delete':
                if args.all:
                    loader.delete_all_repos()
                elif args.repos:
                    for repo in args.repos:
                        loader.delete_repo_by_name(repo)
        except Exception as e:
            ColorPrinter.red(f"runtime error: {str(e).rstrip()}")
        finally:
            ColorPrinter.blue("\nsee you later!")

# uploader

class Uploader:
    """Управляет загрузкой репозиториев на CodeBerg"""

    def __init__(self, token: str, target_dir: str) -> None:
        """
        Принимает токен CodeBerg
        
        Для корректной работы необходимо чтобы токен имел доступ ко всем репозиториям и к информации о пользователе
        """

        self.token = token
        self.target_dir = target_dir

        self.base_url = "https://codeberg.org"
        self.api_url = "https://codeberg.org/api/v1"
        self.api_headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/json"
        }

        self.username = self._get_username()
        self.repos = self._get_repos_info()

    def delete_all_repos(self) -> None:
        """
        Удаление всех репозиториев с CodeBerg
        """

        for r in self.repos:
            self.delete_repo_by_name(r["name"])

    def delete_repo_by_name(self, repo_name: str) -> None:
        """
        **Удаление репозитория по его имени**

        Вернет RuntimeError если что то пошло не так
        """

        ColorPrinter.blue(f"deleting '{repo_name}' from codeberg...")

        response = requests.delete(
            f"{self.api_url}/repos/{self.username}/{repo_name}",
            headers=self.api_headers
        )
        
        if response.status_code != 204:
            raise RuntimeError(f"failed to delete repository {repo_name}: {response.text}")
        
        ColorPrinter.blue(f"deleted '{repo_name}' from сodeberg")

    def upload_all_repos(self) -> None:
        """
        Закидывает/обновляет на codeberg все репозитории из папки
        """

        if not os.path.isdir(self.target_dir):
            raise RuntimeError(f"directory not found: {self.target_dir}")

        for repo in os.listdir(self.target_dir):
            self.upload_repo_by_name(repo)

    def upload_repo_by_name(self, repo_name: str) -> None:
        """
        Закидывает/обновляет репозиторий на codeberg
        """

        # есть ли вообще такая директория?
        local_path = os.path.join(self.target_dir, repo_name)
        if not os.path.isdir(local_path):
            raise RuntimeError(f"directory not found: {local_path}")

        # эта директория - репозиторий?
        is_repo = os.path.isdir(os.path.join(local_path, ".git"))
        if not is_repo:
            raise RuntimeError(f"the directory is not a repository: {local_path}")

        # индикатор приватного репо - файл .private в нем 
        is_private = os.path.exists(os.path.join(local_path, ".private"))

        if not self._repo_exists(repo_name):
            self._create_repo(repo_name, private=is_private)
        else:
            self._update_repo_visibility(repo_name, is_private)

        base = self.base_url.replace("https://", f"https://{self.token}@")
        remote_url = f"{base}/{self.username}/{repo_name}.git"

        try:
            ColorPrinter.blue(f"uploading '{repo_name}' to codeberg...")

            # получение списка удаленных репозиториев
            # возвращает что то типо
            # codeberg
            # origin
            remotes = subprocess.run(
                ["git", "-C", local_path, "remote"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            ).stdout.splitlines()

            if "codeberg" in remotes:
                # уже есть codeberg => обновление ссылочки на всякий случай 
                # (например если репо переименован => старый url не актуален уже)
                subprocess.run(
                    ["git", "-C", local_path, "remote", "set-url", "codeberg", remote_url],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
            else:
                # иначе добавление нового удаленного репо с именем codeberg
                subprocess.run(
                    ["git", "-C", local_path, "remote", "add", "codeberg", remote_url],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )

            # отправка всех веток в удаленный репо
            subprocess.run(
                ["git", "-C", local_path, "push", "--force", "--all", "codeberg"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )

            ColorPrinter.blue(f"uploaded '{repo_name}' to сodeberg")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"git command failed: {e}") from e

    def _update_repo_visibility(self, repo_name: str, private: bool) -> None:
        """
        **Обновляет видимость репозитория**
        
        В случае если статус-код ответа не 200 инициирует RuntimeError
        """
        
        response = requests.patch(
            f"{self.api_url}/repos/{self.username}/{repo_name}",
            headers=self.api_headers,
            json={"private": private}
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"failed to update repository visibility: {response.text}")

    def _create_repo(self, repo_name: str, private: bool = False) -> dict:
        """
        **Создает новый репозиторий на codeberg**
        
        В случае если статус-код ответа не 201 инициирует RuntimeError
        """

        data = {
            "name": repo_name,
            "auto_init": False,
            "private": private
        }
        
        response = requests.post(
            f"{self.api_url}/user/repos",
            headers=self.api_headers,
            json=data
        )
        
        if response.status_code != 201:
            raise RuntimeError(f"failed to create repo: {response.text}")
        
        return response.json()

    def _repo_exists(self, repo_name: str) -> bool:
        """
        Проверяет существование репозитория на CodeBerg
        """

        for r in self.repos:
            if r["name"] == repo_name:
                return True
        return False

    def _get_username(self) -> str:
        """
        **Получает имя пользователя Codeberg по токену**

        В случае если статус-код ответа не 200 инициирует RuntimeError
        """

        response = requests.get(
            f"{self.api_url}/user",
            headers=self.api_headers
        )
        
        if response.status_code != 200:
            raise RuntimeError("failed to get user info")
        
        return response.json()["login"]

    def _get_repos_info(self) -> list[dict]:
        """
        Получает список всех репозиториев
        
        Вернет RuntimeError если что то пошло не так
        """
        page, repos = 1, []
        
        while True:
            response = requests.get(
                f"{self.api_url}/user/repos",
                headers=self.api_headers,
                params={"page": page, "per_page": 100, "type": "owner"}
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