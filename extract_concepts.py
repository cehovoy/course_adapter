#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os
from course_format_detector import get_course_format

def extract_concepts_from_glossary(course_text):
    """
    Извлекает понятия из глоссария в конце курса.
    
    Аргументы:
    - course_text: текст курса
    
    Возвращает:
    - список понятий
    """
    # Извлекаем последние 5000 символов текста (где обычно находится глоссарий)
    last_part = course_text[-10000:] if len(course_text) > 10000 else course_text
    
    # Ищем список понятий в алфавитном порядке
    # В курсе "Практики саморазвития" список понятий находится в самом конце документа
    # и представляет собой список слов через запятую
    concepts = []
    
    # Ищем начало списка понятий - обычно это секция "Понятия", "Глоссарий" или просто список
    glossary_patterns = [
        r"(?:Понятия|Глоссарий|Термины)[:.]?\s*((?:[А-Я][а-яА-Я\- ]+,\s*)+[А-Я][а-яА-Я\- ]+)",
        r"((?:[А-Я][а-яА-Я\- ]+,\s*){10,}[А-Я][а-яА-Я\- ]+)"  # Просто ищем много терминов через запятую
    ]
    
    for pattern in glossary_patterns:
        matches = re.findall(pattern, last_part, re.DOTALL)
        if matches:
            print(f"Найден список понятий из {len(matches)} блоков")
            
            for match in matches:
                # Если match - это кортеж, берем первый элемент
                if isinstance(match, tuple):
                    match = match[0]
                
                # Разделяем по запятым и очищаем
                terms = [term.strip() for term in match.split(',')]
                
                # Добавляем валидные термины в список
                for term in terms:
                    # Проверяем, что это не пустая строка и не содержит нежелательных символов
                    if term and re.match(r'^[А-Я][а-яА-Я\- ]+$', term):
                        concepts.append(term)
    
    # Удаляем дубликаты и возвращаем отсортированный список
    concepts = list(set(concepts))
    concepts.sort()
    
    print(f"Всего извлечено {len(concepts)} уникальных понятий из глоссария")
    if concepts:
        print("Примеры понятий:", concepts[:10])
    
    return concepts

def extract_concepts_from_chapters(course_text):
    """
    Извлекает понятия из секций "Основные понятия" в каждой главе.
    
    Аргументы:
    - course_text: текст курса
    
    Возвращает:
    - список понятий
    """
    concepts = []
    
    # Ищем главы
    chapter_pattern = r"Глава \d+\.\s+([^\n]+)"
    chapter_titles = re.findall(chapter_pattern, course_text)
    
    # Разделение текста на главы
    chapters = re.split(r"Глава \d+\.\s+[^\n]+", course_text)
    chapters = chapters[1:] if len(chapters) > 1 else []
    
    # Для каждой главы ищем секцию "Основные понятия"
    for i, chapter_text in enumerate(chapters):
        if i < len(chapter_titles):
            chapter_title = f"Глава {i+1}: {chapter_titles[i]}"
            print(f"Анализ главы: {chapter_title}")
            
            # Поиск секции "Основные понятия" в саммари раздела
            summary_match = re.search(r"Саммари раздела.*?Основные понятия:(.*?)(?=\n\n|\n[А-Я]|Моделирование:|Вопросы для повторения|$)", 
                                      chapter_text, re.DOTALL)
            
            if summary_match:
                concepts_text = summary_match.group(1).strip()
                print(f"Найдена секция 'Основные понятия' в саммари. Размер текста: {len(concepts_text)} символов")
                
                # Разделяем по запятым и очищаем
                chapter_concepts = [c.strip() for c in concepts_text.split(',')]
                
                # Добавляем валидные понятия
                for concept in chapter_concepts:
                    if concept and re.search(r'[а-яА-Яa-zA-Z]', concept) and len(concept) < 50:
                        concepts.append(concept)
            else:
                # Альтернативный поиск просто по фразе "Основные понятия:"
                basic_concepts_match = re.search(r"Основные понятия:(.*?)(?=\n\n|\n[А-Я]|$)", chapter_text, re.DOTALL)
                if basic_concepts_match:
                    concepts_text = basic_concepts_match.group(1).strip()
                    print(f"Найдена отдельная секция 'Основные понятия'. Размер текста: {len(concepts_text)} символов")
                    
                    # Разделяем по запятым и очищаем
                    chapter_concepts = [c.strip() for c in concepts_text.split(',')]
                    
                    # Добавляем валидные понятия
                    for concept in chapter_concepts:
                        if concept and re.search(r'[а-яА-Яa-zA-Z]', concept) and len(concept) < 50:
                            concepts.append(concept)
    
    # Удаляем дубликаты и возвращаем отсортированный список
    concepts = list(set(concepts))
    concepts.sort()
    
    print(f"Всего извлечено {len(concepts)} уникальных понятий из глав")
    if concepts:
        print("Примеры понятий:", concepts[:10])
    
    return concepts

def extract_course_concepts(course_file, course_format=None):
    """
    Извлекает понятия из курса в зависимости от его формата.
    
    Аргументы:
    - course_file: путь к файлу с текстом курса
    - course_format: формат курса ("chapter-based" или "glossary-based")
    
    Возвращает:
    - список понятий
    """
    try:
        # Чтение текста курса
        with open(course_file, 'r', encoding='utf-8') as file:
            course_text = file.read()
        
        # Определение формата курса, если не задан явно
        if not course_format:
            course_format = get_course_format(course_file)
        
        # Извлечение понятий в зависимости от формата
        if course_format == "glossary-based":
            # Для курса с глоссарием в конце
            concepts = extract_concepts_from_glossary(course_text)
            
            # Если не удалось извлечь достаточно понятий из глоссария,
            # попробуем извлечь их из глав как резервный вариант
            if len(concepts) < 10:
                print("Недостаточно понятий из глоссария, пробуем извлечь из глав...")
                concepts_from_chapters = extract_concepts_from_chapters(course_text)
                concepts.extend(concepts_from_chapters)
                concepts = list(set(concepts))  # Удаляем дубликаты
                concepts.sort()
                
        else:
            # Для курса с понятиями в главах
            concepts = extract_concepts_from_chapters(course_text)
        
        return concepts
    except Exception as e:
        print(f"Ошибка при извлечении понятий из курса: {str(e)}")
        return []

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        format_override = sys.argv[2] if len(sys.argv) > 2 else None
        concepts = extract_course_concepts(file_path, format_override)
        print(f"\nОбнаружено {len(concepts)} понятий в курсе")
        print("\nПервые 20 понятий:")
        for concept in concepts[:20]:
            print(f"- {concept}")
    else:
        print("Использование: python extract_concepts.py путь_к_файлу_курса [формат]")
        print("Формат (опционально): chapter-based или glossary-based") 