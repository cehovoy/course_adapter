import requests
import json
import re
import os
import time
import sys
from adapter import read_course_file, split_into_chapters, analyze_chapter_with_grok, load_to_neo4j
from py2neo import Graph, Node, Relationship

# Добавляем родительскую директорию в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Конфигурация
NEO4J_URI = "bolt://localhost:7687/system_self_development"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j"

def main():
    print("Начинаем полный анализ второй главы курса...")
    
    # Чтение файла курса
    course_text = read_course_file("/home/cehovoy/adapter_course/course.txt")
    print(f"Файл курса успешно прочитан: {len(course_text)} символов")
    
    # Разделение на главы
    chapters = split_into_chapters(course_text)
    print(f"Найдено {len(chapters)} глав")
    
    if len(chapters) < 2:
        print("Недостаточно глав в курсе!")
        return
    
    # Выбираем вторую главу для анализа
    second_chapter = chapters[1]
    print(f"Анализ главы: {second_chapter['title']}")
    print(f"Длина текста главы: {len(second_chapter['content'])} символов")
    print("Первые 200 символов главы:")
    print(second_chapter['content'][:200] + "...")
    
    # Анализ главы с Grok
    print("Начинаем анализ главы с помощью Grok...")
    chapter_analysis = analyze_chapter_with_grok(second_chapter)
    
    if chapter_analysis:
        print("Анализ успешно выполнен!")
        print(f"Выделено {len(chapter_analysis.get('main_ideas', []))} главных мыслей")
        print(f"Найдено {len(chapter_analysis.get('concepts', []))} понятий")
        print(f"Обнаружено {len(chapter_analysis.get('relationships', []))} связей между понятиями")
        
        # Сохранение результатов в JSON
        with open("second_chapter_analysis.json", "w", encoding="utf-8") as f:
            json.dump(chapter_analysis, f, ensure_ascii=False, indent=2)
        print("Результаты анализа сохранены в файл second_chapter_analysis.json")
        
        # Загрузка в Neo4j
        print("\nЗагрузка данных в Neo4j...")
        
        # Подготовка данных для загрузки (имитируем массив глав с одной главой)
        chapters_data = [None, chapter_analysis]  # Помещаем во вторую позицию для правильного индексирования
        
        # Вызов функции загрузки
        success = load_to_neo4j(chapters_data)
        
        if success:
            print("Данные успешно загружены в Neo4j")
            
            # Проверка данных в Neo4j
            print("\nПроверка данных в Neo4j...")
            graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            
            # Проверка узлов
            node_count = graph.run("MATCH (n) RETURN count(n) AS count").data()[0]["count"]
            rel_count = graph.run("MATCH ()-[r]->() RETURN count(r) AS count").data()[0]["count"]
            
            print(f"Общее количество узлов: {node_count}")
            print(f"Общее количество связей: {rel_count}")
            
            # Получение понятий
            concepts = graph.run("""
                MATCH (c:Concept) 
                RETURN c.name AS name
            """).data()
            
            print("\nЗагруженные понятия:")
            for i, concept in enumerate(concepts):
                print(f"{i+1}. {concept['name']}")
            
            # Показать типы связей
            rel_types = graph.run("""
                MATCH ()-[r]->() 
                RETURN DISTINCT type(r) AS type, count(r) AS count 
                ORDER BY count DESC
            """).data()
            
            print("\nТипы связей:")
            for rel_type in rel_types:
                print(f"{rel_type['type']}: {rel_type['count']} связей")
        else:
            print("Не удалось загрузить данные в Neo4j")
    else:
        print("Не удалось проанализировать главу с помощью Grok")
    
    print("\nАнализ завершен")

if __name__ == "__main__":
    main() 