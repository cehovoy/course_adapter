import requests
import json
import re
import os
import time
from adapter import read_course_file, split_into_chapters, analyze_chapter_with_grok

# Основная функция
def main():
    print("Тестирование анализа первой главы курса...")
    
    # Чтение файла курса
    course_text = read_course_file("/home/cehovoy/adapter_course/course.txt")
    print(f"Файл курса успешно прочитан: {len(course_text)} символов")
    
    # Разделение на главы
    chapters = split_into_chapters(course_text)
    print(f"Найдено {len(chapters)} глав")
    
    if not chapters:
        print("Главы не найдены!")
        return
    
    # Анализ только первой главы
    first_chapter = chapters[0]
    print(f"Анализ главы: {first_chapter['title']}")
    print(f"Длина текста главы: {len(first_chapter['content'])} символов")
    print("Первые 200 символов главы:")
    print(first_chapter['content'][:200] + "...")
    
    # Анализ главы с Grok
    chapter_analysis = analyze_chapter_with_grok(first_chapter)
    
    # Сохранение результата в JSON
    with open("first_chapter_analysis.json", "w", encoding="utf-8") as f:
        if chapter_analysis:
            print("Анализ успешно выполнен!")
            print(f"Найдено {len(chapter_analysis.get('concepts', []))} понятий и {len(chapter_analysis.get('relationships', []))} связей")
            json.dump(chapter_analysis, f, ensure_ascii=False, indent=2)
        else:
            print("Не удалось проанализировать главу")
            json.dump({}, f)
    
    print("Тестирование завершено")

if __name__ == "__main__":
    main() 