#!/usr/bin/env python3
"""
Запуск всех unit-тестов проекта

Использование:
    python run_tests.py
    python run_tests.py -v  # Подробный вывод
"""
import unittest
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == '__main__':
    # Находим все тесты в директории tests/
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')

    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Выводим статистику
    print("\n" + "="*70)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*70)
    print(f"✅ Пройдено: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Провалено: {len(result.failures)}")
    print(f"⚠️  Ошибок: {len(result.errors)}")
    print("="*70)

    # Возвращаем код выхода (0 = успех, 1 = есть ошибки)
    sys.exit(0 if result.wasSuccessful() else 1)
