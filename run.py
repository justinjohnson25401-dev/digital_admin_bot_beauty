#!/usr/bin/env python3
"""
Единый лаунчер для запуска клиентского и админ-бота одной командой.
Использование: python run.py
"""

import subprocess
import sys
import os
import signal
import time
from threading import Thread

# Цвета для терминала
class Colors:
    CLIENT = '\033[94m'  # Синий
    ADMIN = '\033[92m'   # Зелёный
    ERROR = '\033[91m'   # Красный
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header():
    print(f"""
{Colors.BOLD}╔══════════════════════════════════════════════════════╗
║     🚀 ЗАПУСК БОТОВ САЛОНА КРАСОТЫ                   ║
╠══════════════════════════════════════════════════════╣
║  {Colors.CLIENT}[CLIENT]{Colors.RESET}{Colors.BOLD} Клиентский бот  │  {Colors.ADMIN}[ADMIN]{Colors.RESET}{Colors.BOLD} Админ-панель   ║
╚══════════════════════════════════════════════════════╝{Colors.RESET}
""")

def stream_output(process, prefix, color):
    """Читает вывод процесса и печатает с префиксом"""
    for line in iter(process.stdout.readline, ''):
        if line:
            print(f"{color}[{prefix}]{Colors.RESET} {line.strip()}")
    process.stdout.close()

def stream_errors(process, prefix, color):
    """Читает stderr процесса"""
    for line in iter(process.stderr.readline, ''):
        if line:
            print(f"{color}[{prefix}]{Colors.RESET} {Colors.ERROR}{line.strip()}{Colors.RESET}")
    process.stderr.close()

def main():
    print_header()

    # Проверяем наличие .env
    if not os.path.exists('.env'):
        print(f"{Colors.ERROR}❌ Файл .env не найден!{Colors.RESET}")
        print("   Сначала запустите: python setup.py")
        sys.exit(1)

    # Проверяем наличие конфига
    if not os.path.exists('config'):
        print(f"{Colors.ERROR}❌ Папка config не найдена!{Colors.RESET}")
        print("   Сначала запустите: python setup.py")
        sys.exit(1)

    processes = []
    threads = []

    try:
        # Запускаем клиентского бота
        print(f"{Colors.CLIENT}▶ Запуск клиентского бота...{Colors.RESET}")
        client = subprocess.Popen(
            [sys.executable, 'main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        processes.append(('CLIENT', client))

        # Потоки для вывода клиента
        t1 = Thread(target=stream_output, args=(client, 'CLIENT', Colors.CLIENT), daemon=True)
        t2 = Thread(target=stream_errors, args=(client, 'CLIENT', Colors.CLIENT), daemon=True)
        threads.extend([t1, t2])
        t1.start()
        t2.start()

        time.sleep(1)  # Даём клиенту стартовать первым

        # Запускаем админ-бота
        print(f"{Colors.ADMIN}▶ Запуск админ-бота...{Colors.RESET}")
        admin = subprocess.Popen(
            [sys.executable, 'admin_bot/main.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        processes.append(('ADMIN', admin))

        # Потоки для вывода админа
        t3 = Thread(target=stream_output, args=(admin, 'ADMIN', Colors.ADMIN), daemon=True)
        t4 = Thread(target=stream_errors, args=(admin, 'ADMIN', Colors.ADMIN), daemon=True)
        threads.extend([t3, t4])
        t3.start()
        t4.start()

        print(f"\n{Colors.BOLD}✅ Оба бота запущены! Нажмите Ctrl+C для остановки.{Colors.RESET}\n")
        print("=" * 55)

        # Ждём завершения любого из процессов
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"\n{Colors.ERROR}⚠ {name} завершился с кодом {ret}{Colors.RESET}")
                    raise KeyboardInterrupt
            time.sleep(0.5)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.BOLD}🛑 Остановка ботов...{Colors.RESET}")

        for name, proc in processes:
            if proc.poll() is None:
                print(f"   Останавливаю {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

        print(f"{Colors.BOLD}✅ Все боты остановлены.{Colors.RESET}\n")

if __name__ == '__main__':
    main()
