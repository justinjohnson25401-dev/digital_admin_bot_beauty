"""
Тесты для модуля validators
"""
import pytest
from utils.validators import (
    is_valid_phone,
    clean_phone,
    validate_russian_phone,
    validate_business_name,
    validate_work_hours,
    validate_slot_duration,
    validate_service_name,
    validate_price
)


class TestPhoneValidation:
    """Тесты валидации телефонных номеров"""

    def test_valid_phone_russian_format(self):
        """Российский номер в формате +7 валиден"""
        assert is_valid_phone("+79991234567") == True

    def test_valid_phone_without_plus(self):
        """Номер без + валиден"""
        assert is_valid_phone("79991234567") == True

    def test_invalid_phone_too_short(self):
        """Слишком короткий номер невалиден"""
        assert is_valid_phone("123") == False

    def test_clean_phone_removes_spaces(self):
        """clean_phone удаляет пробелы"""
        assert clean_phone("+7 999 123 45 67") == "+79991234567"

    def test_clean_phone_removes_dashes(self):
        """clean_phone удаляет дефисы"""
        assert clean_phone("+7-999-123-45-67") == "+79991234567"

    def test_clean_phone_removes_parentheses(self):
        """clean_phone удаляет скобки"""
        assert clean_phone("+7(999)123-45-67") == "+79991234567"


class TestRussianPhoneValidation:
    """Тесты строгой валидации российских номеров"""

    def test_valid_plus7_format(self):
        """Номер +7XXXXXXXXXX валиден"""
        is_valid, error = validate_russian_phone("+79991234567")
        assert is_valid == True
        assert error is None

    def test_valid_8_format(self):
        """Номер 8XXXXXXXXXX валиден"""
        is_valid, error = validate_russian_phone("89991234567")
        assert is_valid == True
        assert error is None

    def test_invalid_empty(self):
        """Пустой номер невалиден"""
        is_valid, error = validate_russian_phone("")
        assert is_valid == False
        assert error is not None

    def test_invalid_short_plus7(self):
        """Короткий номер +7 невалиден"""
        is_valid, error = validate_russian_phone("+7999123")
        assert is_valid == False
        assert "12 символов" in error


class TestBusinessNameValidation:
    """Тесты валидации названия бизнеса"""

    def test_valid_name(self):
        """Корректное название проходит валидацию"""
        is_valid, error = validate_business_name("Салон Красоты")
        assert is_valid == True
        assert error is None

    def test_name_too_short(self):
        """Слишком короткое название"""
        is_valid, error = validate_business_name("AB")
        assert is_valid == False
        assert "короткое" in error

    def test_name_too_long(self):
        """Слишком длинное название"""
        is_valid, error = validate_business_name("A" * 60)
        assert is_valid == False
        assert "длинное" in error

    def test_name_empty(self):
        """Пустое название"""
        is_valid, error = validate_business_name("")
        assert is_valid == False

    def test_name_with_forbidden_chars(self):
        """Название с запрещёнными символами"""
        is_valid, error = validate_business_name("Salon <script>")
        assert is_valid == False
        assert "запрещённый" in error


class TestWorkHoursValidation:
    """Тесты валидации часов работы"""

    def test_valid_hours(self):
        """Корректные часы работы"""
        is_valid, error = validate_work_hours(10, 20)
        assert is_valid == True
        assert error is None

    def test_start_greater_than_end(self):
        """Начало позже конца"""
        is_valid, error = validate_work_hours(20, 10)
        assert is_valid == False
        assert "меньше" in error

    def test_start_equals_end(self):
        """Начало равно концу"""
        is_valid, error = validate_work_hours(10, 10)
        assert is_valid == False

    def test_invalid_start_hour(self):
        """Некорректный час начала"""
        is_valid, error = validate_work_hours(25, 20)
        assert is_valid == False
        assert "0 до 23" in error

    def test_invalid_end_hour(self):
        """Некорректный час конца"""
        is_valid, error = validate_work_hours(10, -1)
        assert is_valid == False


class TestSlotDurationValidation:
    """Тесты валидации длительности слота"""

    def test_valid_duration(self):
        """Корректная длительность"""
        is_valid, error = validate_slot_duration(60)
        assert is_valid == True
        assert error is None

    def test_duration_too_short(self):
        """Слишком короткий слот"""
        is_valid, error = validate_slot_duration(10)
        assert is_valid == False
        assert "15 минут" in error

    def test_duration_too_long(self):
        """Слишком длинный слот"""
        is_valid, error = validate_slot_duration(500)
        assert is_valid == False
        assert "480" in error

    def test_duration_not_multiple_of_15(self):
        """Длительность не кратна 15"""
        is_valid, error = validate_slot_duration(25)
        assert is_valid == False
        assert "кратную 15" in error

    def test_valid_durations(self):
        """Проверка различных валидных значений"""
        for duration in [15, 30, 45, 60, 90, 120]:
            is_valid, error = validate_slot_duration(duration)
            assert is_valid == True, f"Duration {duration} should be valid"


class TestServiceNameValidation:
    """Тесты валидации названия услуги"""

    def test_valid_service_name(self):
        """Корректное название услуги"""
        is_valid, error = validate_service_name("Стрижка")
        assert is_valid == True

    def test_service_name_too_short(self):
        """Слишком короткое название"""
        is_valid, error = validate_service_name("A")
        assert is_valid == False
        assert "короткое" in error

    def test_service_name_too_long(self):
        """Слишком длинное название"""
        is_valid, error = validate_service_name("A" * 150)
        assert is_valid == False
        assert "длинное" in error


class TestPriceValidation:
    """Тесты валидации цены"""

    def test_valid_price(self):
        """Корректная цена"""
        is_valid, error = validate_price(1500)
        assert is_valid == True

    def test_zero_price(self):
        """Нулевая цена валидна"""
        is_valid, error = validate_price(0)
        assert is_valid == True

    def test_negative_price(self):
        """Отрицательная цена"""
        is_valid, error = validate_price(-100)
        assert is_valid == False
        assert "отрицательной" in error

    def test_price_too_high(self):
        """Слишком высокая цена"""
        is_valid, error = validate_price(2000000)
        assert is_valid == False
        assert "высокая" in error

    def test_price_not_integer(self):
        """Нецелое значение цены"""
        is_valid, error = validate_price("abc")
        assert is_valid == False
        assert "целым числом" in error


class TestMessageTextValidation:
    """Тесты валидации текста сообщений"""

    def test_valid_message_text(self):
        """Корректный текст сообщения"""
        from utils.validators import validate_message_text
        is_valid, error = validate_message_text("Добро пожаловать в наш салон!")
        assert is_valid == True
        assert error is None

    def test_message_text_too_short(self):
        """Слишком короткий текст"""
        from utils.validators import validate_message_text
        is_valid, error = validate_message_text("Hi")
        assert is_valid == False
        assert "короткий" in error

    def test_message_text_too_long(self):
        """Слишком длинный текст"""
        from utils.validators import validate_message_text
        is_valid, error = validate_message_text("A" * 2500)
        assert is_valid == False
        assert "длинный" in error

    def test_message_text_empty(self):
        """Пустой текст"""
        from utils.validators import validate_message_text
        is_valid, error = validate_message_text("")
        assert is_valid == False

    def test_message_text_with_script(self):
        """Текст с тегом script"""
        from utils.validators import validate_message_text
        is_valid, error = validate_message_text("Hello <script>alert('xss')</script>")
        assert is_valid == False
        assert "запрещённый" in error

    def test_message_text_with_onerror(self):
        """Текст с атрибутом onerror"""
        from utils.validators import validate_message_text
        is_valid, error = validate_message_text('<img onerror="alert(1)" src="x">')
        assert is_valid == False
        assert "запрещённый" in error

    def test_message_text_with_javascript(self):
        """Текст с javascript:"""
        from utils.validators import validate_message_text
        is_valid, error = validate_message_text('<a href="javascript:alert(1)">Click</a>')
        assert is_valid == False
        assert "запрещённый" in error

    def test_message_text_with_safe_html(self):
        """Текст с безопасным HTML (bold, italic)"""
        from utils.validators import validate_message_text
        is_valid, error = validate_message_text("<b>Важно!</b> Текст с <i>форматированием</i>")
        assert is_valid == True


class TestFaqButtonValidation:
    """Тесты валидации кнопки FAQ"""

    def test_valid_faq_button(self):
        """Корректная кнопка FAQ"""
        from utils.validators import validate_faq_button
        is_valid, error = validate_faq_button("Цены")
        assert is_valid == True
        assert error is None

    def test_faq_button_with_emoji(self):
        """Кнопка с эмодзи"""
        from utils.validators import validate_faq_button
        is_valid, error = validate_faq_button("💰 Цены")
        assert is_valid == True

    def test_faq_button_empty(self):
        """Пустая кнопка"""
        from utils.validators import validate_faq_button
        is_valid, error = validate_faq_button("")
        assert is_valid == False

    def test_faq_button_too_long(self):
        """Слишком длинная кнопка"""
        from utils.validators import validate_faq_button
        is_valid, error = validate_faq_button("A" * 70)
        assert is_valid == False
        assert "длинный" in error

    def test_faq_button_with_newline(self):
        """Кнопка с переносом строки"""
        from utils.validators import validate_faq_button
        is_valid, error = validate_faq_button("Цены\nи услуги")
        assert is_valid == False
        assert "переносы" in error

    def test_faq_button_max_length(self):
        """Кнопка максимальной длины (64 символа)"""
        from utils.validators import validate_faq_button
        is_valid, error = validate_faq_button("A" * 64)
        assert is_valid == True


class TestFaqAnswerValidation:
    """Тесты валидации ответа FAQ"""

    def test_valid_faq_answer(self):
        """Корректный ответ FAQ"""
        from utils.validators import validate_faq_answer
        is_valid, error = validate_faq_answer("Наши цены: стрижка - 1000р, окрашивание - 3000р")
        assert is_valid == True
        assert error is None

    def test_faq_answer_multiline(self):
        """Многострочный ответ FAQ"""
        from utils.validators import validate_faq_answer
        is_valid, error = validate_faq_answer("Часы работы:\nПн-Пт: 10:00-20:00\nСб: 10:00-18:00\nВс: выходной")
        assert is_valid == True

    def test_faq_answer_too_short(self):
        """Слишком короткий ответ"""
        from utils.validators import validate_faq_answer
        is_valid, error = validate_faq_answer("Да")
        assert is_valid == False
        assert "короткий" in error

    def test_faq_answer_too_long(self):
        """Слишком длинный ответ"""
        from utils.validators import validate_faq_answer
        is_valid, error = validate_faq_answer("A" * 2500)
        assert is_valid == False
        assert "длинный" in error

    def test_faq_answer_with_script(self):
        """Ответ с тегом script"""
        from utils.validators import validate_faq_answer
        is_valid, error = validate_faq_answer("Ответ <script>evil()</script> текст")
        assert is_valid == False
        assert "запрещённый" in error

    def test_faq_answer_with_iframe(self):
        """Ответ с тегом iframe"""
        from utils.validators import validate_faq_answer
        is_valid, error = validate_faq_answer('Текст <iframe src="evil.com"></iframe>')
        assert is_valid == False
        assert "запрещённый" in error

    def test_faq_answer_empty(self):
        """Пустой ответ"""
        from utils.validators import validate_faq_answer
        is_valid, error = validate_faq_answer("")
        assert is_valid == False


class TestMasterNameValidation:
    """Тесты валидации имени мастера"""

    def test_valid_master_name_simple(self):
        """Простое имя"""
        from utils.validators import validate_master_name
        is_valid, error = validate_master_name("Анна")
        assert is_valid == True
        assert error is None

    def test_valid_master_name_with_surname(self):
        """Имя с фамилией"""
        from utils.validators import validate_master_name
        is_valid, error = validate_master_name("Анна Петрова")
        assert is_valid == True

    def test_valid_master_name_with_hyphen(self):
        """Имя с дефисом"""
        from utils.validators import validate_master_name
        is_valid, error = validate_master_name("Ольга-стилист")
        assert is_valid == True

    def test_master_name_too_short(self):
        """Слишком короткое имя"""
        from utils.validators import validate_master_name
        is_valid, error = validate_master_name("А")
        assert is_valid == False
        assert "короткое" in error

    def test_master_name_too_long(self):
        """Слишком длинное имя"""
        from utils.validators import validate_master_name
        is_valid, error = validate_master_name("А" * 60)
        assert is_valid == False
        assert "длинное" in error

    def test_master_name_empty(self):
        """Пустое имя"""
        from utils.validators import validate_master_name
        is_valid, error = validate_master_name("")
        assert is_valid == False

    def test_master_name_with_invalid_chars(self):
        """Имя с недопустимыми символами"""
        from utils.validators import validate_master_name
        is_valid, error = validate_master_name("Анна<script>")
        assert is_valid == False
        assert "недопустимые" in error

    def test_master_name_with_numbers(self):
        """Имя с цифрами (допустимо по паттерну \\w)"""
        from utils.validators import validate_master_name
        is_valid, error = validate_master_name("Мастер1")
        assert is_valid == True


class TestMasterRoleValidation:
    """Тесты валидации роли мастера"""

    def test_valid_master_role(self):
        """Корректная роль"""
        from utils.validators import validate_master_role
        is_valid, error = validate_master_role("Стилист")
        assert is_valid == True
        assert error is None

    def test_master_role_empty(self):
        """Пустая роль (допустимо)"""
        from utils.validators import validate_master_role
        is_valid, error = validate_master_role("")
        assert is_valid == True

    def test_master_role_none(self):
        """None роль (допустимо)"""
        from utils.validators import validate_master_role
        is_valid, error = validate_master_role(None)
        assert is_valid == True

    def test_master_role_whitespace(self):
        """Роль из пробелов (допустимо после strip)"""
        from utils.validators import validate_master_role
        is_valid, error = validate_master_role("   ")
        assert is_valid == True

    def test_master_role_too_long(self):
        """Слишком длинная роль"""
        from utils.validators import validate_master_role
        is_valid, error = validate_master_role("А" * 60)
        assert is_valid == False
        assert "длинная" in error

    def test_master_role_with_script(self):
        """Роль с тегом script"""
        from utils.validators import validate_master_role
        is_valid, error = validate_master_role("Стилист<script>")
        assert is_valid == False
        assert "запрещённый" in error

    def test_master_role_normal(self):
        """Обычная роль со спецсимволами"""
        from utils.validators import validate_master_role
        is_valid, error = validate_master_role("Топ-стилист / колорист")
        assert is_valid == True


class TestDateFormatValidation:
    """Тесты валидации формата даты"""

    def test_valid_date_format(self):
        """Корректный формат даты"""
        from utils.validators import validate_date_format
        is_valid, error = validate_date_format("2026-01-15")
        assert is_valid == True
        assert error is None

    def test_valid_date_past(self):
        """Дата в прошлом (формат валиден)"""
        from utils.validators import validate_date_format
        is_valid, error = validate_date_format("2020-12-31")
        assert is_valid == True

    def test_valid_date_future(self):
        """Дата в будущем"""
        from utils.validators import validate_date_format
        is_valid, error = validate_date_format("2030-06-15")
        assert is_valid == True

    def test_invalid_date_format_dots(self):
        """Неверный формат с точками"""
        from utils.validators import validate_date_format
        is_valid, error = validate_date_format("15.01.2026")
        assert is_valid == False
        assert "YYYY-MM-DD" in error

    def test_invalid_date_format_slashes(self):
        """Неверный формат со слэшами"""
        from utils.validators import validate_date_format
        is_valid, error = validate_date_format("2026/01/15")
        assert is_valid == False

    def test_invalid_month(self):
        """Несуществующий месяц"""
        from utils.validators import validate_date_format
        is_valid, error = validate_date_format("2026-13-01")
        assert is_valid == False

    def test_invalid_day(self):
        """Несуществующий день"""
        from utils.validators import validate_date_format
        is_valid, error = validate_date_format("2026-02-30")
        assert is_valid == False

    def test_invalid_date_text(self):
        """Текст вместо даты"""
        from utils.validators import validate_date_format
        is_valid, error = validate_date_format("abc")
        assert is_valid == False

    def test_date_empty(self):
        """Пустая дата"""
        from utils.validators import validate_date_format
        is_valid, error = validate_date_format("")
        assert is_valid == False
