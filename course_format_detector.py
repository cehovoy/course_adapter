#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os

def detect_course_format(course_text):
    """
    Определяет формат курса автоматически.
    
    Возвращает:
    - "chapter-based": если понятия определены в каждой главе
    - "glossary-based": если в конце курса есть общий список понятий
    """
    # Проверяем наличие глав с шаблоном "Глава X. Название главы"
    chapter_pattern = r"Глава \d+\.\s+([^\n]+)"
    chapter_matches = re.findall(chapter_pattern, course_text)
    
    # Проверяем наличие алфавитного глоссария в конце текста
    # Глоссарий обычно представлен в виде списка понятий в алфавитном порядке
    # Для его обнаружения ищем блок текста с большим количеством терминов через запятую
    glossary_pattern = r"(([А-Я][а-яА-Я]+,\s+){10,})" # Минимум 10 терминов через запятую
    
    # Также проверим характерный признак глоссария - много слов с большой буквы в конце документа
    last_part = course_text[-5000:] if len(course_text) > 5000 else course_text
    capitalized_terms = re.findall(r"([А-Я][а-яА-Я]+)", last_part)
    
    # Проверяем наличие секций "Основные понятия" в главах
    basic_concepts_pattern = r"Основные понятия:(.*?)(?=\n\n|\n[А-Я]|$)"
    basic_concepts_matches = re.findall(basic_concepts_pattern, course_text, re.DOTALL)
    
    # Если нашли главы и в них есть секции с основными понятиями
    if chapter_matches and basic_concepts_matches:
        return "chapter-based"
    
    # Если нашли главы, но не нашли секции с основными понятиями,
    # и при этом в конце документа есть много терминов с большой буквы
    if chapter_matches and len(capitalized_terms) > 100:
        # Проверяем, что большинство терминов находится в последней части документа
        terms_in_last_part = len(capitalized_terms)
        terms_in_first_part = len(re.findall(r"([А-Я][а-яА-Я]+)", course_text[:5000])) if len(course_text) > 5000 else 0
        
        if terms_in_last_part > terms_in_first_part * 2:  # Если в конце терминов в 2 раза больше
            return "glossary-based"
    
    # По умолчанию считаем, что понятия распределены по главам
    return "chapter-based"

def get_course_format(course_file, force_format=None):
    """
    Определяет формат курса на основе содержимого файла или принудительного параметра.
    
    Аргументы:
    - course_file: путь к файлу с текстом курса
    - force_format: принудительно установить формат ("chapter-based" или "glossary-based")
    
    Возвращает:
    - строку с форматом курса
    """
    if force_format in ["chapter-based", "glossary-based"]:
        print(f"Формат курса принудительно установлен как: {force_format}")
        return force_format
    
    try:
        with open(course_file, 'r', encoding='utf-8') as file:
            course_text = file.read()
        
        detected_format = detect_course_format(course_text)
        print(f"Автоматически определен формат курса: {detected_format}")
        return detected_format
    except Exception as e:
        print(f"Ошибка при определении формата курса: {str(e)}")
        print("Используется формат по умолчанию: chapter-based")
        return "chapter-based"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        format_override = sys.argv[2] if len(sys.argv) > 2 else None
        format_result = get_course_format(file_path, format_override)
        print(f"Формат курса: {format_result}")
    else:
        print("Использование: python course_format_detector.py путь_к_файлу_курса [формат]")
        print("Формат (опционально): chapter-based или glossary-based") 