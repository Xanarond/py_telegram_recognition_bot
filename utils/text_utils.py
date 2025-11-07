"""
Утилиты для работы с текстом и предотвращения ошибок форматирования
"""
import re
from typing import Optional


def clean_text_for_telegram(text: str) -> str:
    """
    Очищает текст от потенциально проблемных символов для Telegram
    """
    if not text:
        return ""
    
    # Убираем контролирующие символы
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Заменяем потенциально проблемные последовательности
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Убираем множественные переносы строк
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def find_problematic_markdown(text: str) -> Optional[int]:
    """
    Находит позицию потенциально проблемного символа Markdown
    Возвращает byte offset проблемного места или None
    """
    if not text:
        return None
    
    # Проверяем незакрытые блоки форматирования
    bold_positions = []
    code_positions = []
    
    i = 0
    while i < len(text):
        if text[i:i+2] == '**':
            bold_positions.append(i)
            i += 2
        elif text[i] == '`':
            code_positions.append(i)
            i += 1
        else:
            i += 1
    
    # Проверяем четность
    if len(bold_positions) % 2 != 0:
        return bold_positions[-1]  # Последний незакрытый
    
    if len(code_positions) % 2 != 0:
        return code_positions[-1]  # Последний незакрытый
    
    return None


def fix_markdown_at_position(text: str, position: int) -> str:
    """
    Пытается исправить Markdown разметку в указанной позиции
    """
    if not text or position >= len(text):
        return text
    
    # Если проблема в bold (**), добавляем закрывающий или убираем
    if position >= 1 and text[position-1:position+1] == '**':
        # Если это открывающий **, пытаемся найти закрывающий
        remaining = text[position+1:]
        if '**' not in remaining:
            # Нет закрывающего, убираем открывающий
            return text[:position-1] + text[position+1:]
    
    # Если проблема в code (`), добавляем закрывающий или убираем
    if text[position] == '`':
        remaining = text[position+1:]
        if '`' not in remaining:
            # Нет закрывающего, убираем открывающий
            return text[:position] + text[position+1:]
    
    return text


def safe_truncate_at_word(text: str, max_length: int) -> str:
    """
    Безопасно обрезает текст по границе слов, сохраняя корректность Markdown
    """
    if len(text) <= max_length:
        return text
    
    # Обрезаем с запасом для безопасности
    safe_length = max_length - 10
    
    # Ищем ближайшую границу слова
    truncated = text[:safe_length]
    last_space = truncated.rfind(' ')
    
    if last_space > safe_length * 0.8:  # Если граница слова не слишком далеко
        truncated = truncated[:last_space]
    
    # Проверяем корректность Markdown после обрезки
    problematic_pos = find_problematic_markdown(truncated)
    if problematic_pos is not None:
        # Если есть проблема, обрезаем до проблемного места
        truncated = truncated[:problematic_pos]
        # Ищем предыдущую границу слова
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
    
    return truncated.strip() + "..."


def estimate_message_byte_size(text: str) -> int:
    """
    Оценивает размер сообщения в байтах для Telegram
    """
    return len(text.encode('utf-8'))


def validate_telegram_message(text: str) -> tuple[bool, str]:
    """
    Валидирует сообщение для Telegram
    Возвращает (is_valid, error_message)
    """
    if not text:
        return True, ""
    
    # Проверка длины
    byte_size = estimate_message_byte_size(text)
    if byte_size > 4096:
        return False, f"Сообщение слишком длинное: {byte_size} байт"
    
    # Проверка Markdown
    problematic_pos = find_problematic_markdown(text)
    if problematic_pos is not None:
        return False, f"Некорректная Markdown разметка в позиции {problematic_pos}"
    
    return True, ""
