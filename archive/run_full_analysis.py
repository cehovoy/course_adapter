#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
from adapter import (
    read_course_file, 
    split_into_chapters, 
    analyze_chapter_with_grok, 
    load_to_neo4j
)
from export_graph import export_knowledge_graph, export_system_development_subgraph
from dotenv import load_dotenv
from create_course import create_course

# Загрузка переменных окружения
load_dotenv()

# Парсинг аргументов командной строки
def parse_args():
    parser = argparse.ArgumentParser(description='Анализ курса и загрузка в Neo4j')
    parser.add_argument('--course', type=str, default="Системное саморазвитие",
                        help='Название курса (по умолчанию: "Системное саморазвитие")')
    parser.add_argument('--course-file', type=str, default=os.getenv("COURSE_FILE", "course.txt"),
                        help='Путь к файлу с текстом курса')
    return parser.parse_args()

def run_full_analysis(course_name, course_file):
    # Конфигурация
    RESULTS_DIR = os.getenv("RESULTS_DIR", "results")

    # Убедитесь, что директория для результатов существует
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
        print(f"Создана директория {RESULTS_DIR} для сохранения результатов")

    # Создаем или получаем узел курса
    course_node = create_course(course_name)
    if not course_node:
        print(f"Ошибка: Не удалось создать/найти курс '{course_name}'")
        return False

    try:
        # Шаг 1: Чтение файла курса
        print(f"Чтение файла курса {course_file}...")
        course_text = read_course_file(course_file)
        if not course_text:
            print("Не удалось прочитать файл курса")
            return False
        
        print(f"Файл курса успешно прочитан, {len(course_text)} символов")
        
        # Шаг 2: Разбиение на главы
        print("Разбиение курса на главы...")
        chapters = split_into_chapters(course_text)
        if not chapters:
            print("Не удалось разделить курс на главы")
            return False
        
        print(f"Курс успешно разделен на {len(chapters)} глав")
        
        # Список для хранения результатов по главам
        all_chapters_results = []
        
        # Шаг 3-4: Анализ каждой главы и загрузка в Neo4j
        for i, chapter_text in enumerate(chapters):
            print(f"\nАнализ главы {i+1} из {len(chapters)}...")
            
            # Проверка на мин. размер главы
            if len(chapter_text) < 500:
                print(f"Глава {i+1} слишком короткая ({len(chapter_text)} символов), пропускаем")
                all_chapters_results.append(None)
                continue
            
            # Анализ главы
            chapter_results = analyze_chapter_with_grok(chapter_text)
            
            if not chapter_results:
                print(f"Не удалось проанализировать главу {i+1}")
                all_chapters_results.append(None)
                continue
            
            # Добавим номер главы и краткое название
            chapter_title = chapter_results.get("chapter_title", f"Глава {i+1}")
            chapter_results["chapter_number"] = i + 1
            chapter_results["chapter_title"] = chapter_title
            
            # Сохраняем результаты анализа главы
            result_file = os.path.join(RESULTS_DIR, f"chapter_{i+1}_results.json")
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(chapter_results, f, ensure_ascii=False, indent=2)
            
            print(f"Результаты анализа главы {i+1} сохранены в {result_file}")
            all_chapters_results.append(chapter_results)
        
        # Шаг 5: Загрузка результатов в Neo4j
        print("\nЗагрузка результатов анализа в Neo4j...")
        load_success = load_to_neo4j(all_chapters_results, course_name)
        
        if load_success:
            print("Данные успешно загружены в Neo4j")
            
            # Экспорт графа знаний
            print("\nЭкспорт графа знаний...")
            export_success = export_knowledge_graph(course_name)
            
            if export_success:
                print(f"Граф знаний успешно экспортирован")
            else:
                print("Не удалось экспортировать граф знаний")
            
            return True
        else:
            print("Не удалось загрузить данные в Neo4j")
            return False
            
    except Exception as e:
        print(f"Ошибка при выполнении анализа: {str(e)}")
        return False

if __name__ == "__main__":
    args = parse_args()
    print(f"Запуск полного анализа для курса: '{args.course}'")
    print(f"Файл курса: {args.course_file}")
    success = run_full_analysis(args.course, args.course_file)
    
    if success:
        print("\nПолный анализ успешно завершен!")
    else:
        print("\nПолный анализ завершен с ошибками")
        sys.exit(1) 