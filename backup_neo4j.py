#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import argparse
import shutil
from datetime import datetime
from py2neo import Graph, Node, Relationship
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Параметры подключения к Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

def backup_database(output_dir=None):
    """Создает резервную копию базы данных Neo4j"""
    if output_dir is None:
        output_dir = "backups"
    
    # Создаем директорию для бэкапов, если её нет
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Подключаемся к Neo4j
    try:
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print(f"Соединение с Neo4j установлено: {NEO4J_URI}")
    except Exception as e:
        print(f"Ошибка подключения к Neo4j: {str(e)}")
        return False
    
    # Формируем имя файла с временной меткой
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(output_dir, f"neo4j_backup_{timestamp}.json")
    
    # Получаем все узлы и отношения из базы
    print("Получение узлов и отношений из базы данных...")
    
    # Получаем все курсы
    courses = graph.run("""
        MATCH (c:Course)
        RETURN c
    """).data()
    
    # Получаем все главы
    chapters = graph.run("""
        MATCH (ch:Chapter)
        RETURN ch
    """).data()
    
    # Получаем все понятия
    concepts = graph.run("""
        MATCH (c:Concept)
        RETURN c
    """).data()
    
    # Получаем все отношения
    relationships = graph.run("""
        MATCH ()-[r]->()
        RETURN DISTINCT type(r) AS type, count(r) AS count
    """).data()
    
    # Подробные данные о связях
    relationships_data = graph.run("""
        MATCH (n1)-[r]->(n2)
        RETURN id(n1) AS source_id, n1.name AS source_name, labels(n1) AS source_labels,
               id(n2) AS target_id, n2.name AS target_name, labels(n2) AS target_labels,
               type(r) AS relationship_type, r.description AS description
    """).data()
    
    # Формируем структуру бэкапа
    backup_data = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "neo4j_uri": NEO4J_URI,
            "version": "1.0"
        },
        "nodes": {
            "courses": courses,
            "chapters": chapters,
            "concepts": concepts
        },
        "relationships": {
            "summary": relationships,
            "details": relationships_data
        }
    }
    
    # Сохраняем в JSON файл
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        print(f"Резервная копия успешно создана: {backup_file}")
        print(f"Содержит: {len(courses)} курсов, {len(chapters)} глав, {len(concepts)} понятий, {len(relationships_data)} связей")
        
        return backup_file
    except Exception as e:
        print(f"Ошибка при создании резервной копии: {str(e)}")
        return False

def restore_database(backup_file):
    """Восстанавливает базу данных из резервной копии"""
    if not os.path.exists(backup_file):
        print(f"Ошибка: файл резервной копии не найден: {backup_file}")
        return False
    
    # Подключаемся к Neo4j
    try:
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print(f"Соединение с Neo4j установлено: {NEO4J_URI}")
    except Exception as e:
        print(f"Ошибка подключения к Neo4j: {str(e)}")
        return False
    
    # Загружаем данные из резервной копии
    try:
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        print(f"Загружена резервная копия: {backup_file}")
        print(f"Дата создания: {backup_data['metadata']['created_at']}")
    except Exception as e:
        print(f"Ошибка при чтении файла резервной копии: {str(e)}")
        return False
    
    # Создаем резервную копию текущей базы перед восстановлением
    print("Создание резервной копии текущей базы данных перед восстановлением...")
    backup_before_restore = backup_database("backups/before_restore")
    
    # Запрашиваем подтверждение
    confirmation = input("Вы уверены, что хотите очистить текущую базу данных и восстановить данные из резервной копии? (y/n): ")
    if confirmation.lower() != 'y':
        print("Восстановление отменено.")
        return False
    
    # Очищаем текущую базу данных
    print("Очистка базы данных...")
    graph.run("MATCH (n) DETACH DELETE n")
    
    # Восстанавливаем узлы
    print("Восстановление узлов...")
    # Восстанавливаем курсы
    for course_data in backup_data["nodes"]["courses"]:
        course = course_data["c"]
        course_node = Node("Course", **course)
        graph.create(course_node)
        print(f"Восстановлен курс: {course.get('name', 'Без имени')}")
    
    # Восстанавливаем главы
    for chapter_data in backup_data["nodes"]["chapters"]:
        chapter = chapter_data["ch"]
        chapter_node = Node("Chapter", **chapter)
        graph.create(chapter_node)
        print(f"Восстановлена глава: {chapter.get('title', 'Без названия')}")
    
    # Восстанавливаем понятия
    for concept_data in backup_data["nodes"]["concepts"]:
        concept = concept_data["c"]
        concept_node = Node("Concept", **concept)
        graph.create(concept_node)
    
    print(f"Восстановлено {len(backup_data['nodes']['concepts'])} понятий")
    
    # Восстанавливаем связи
    print("Восстановление связей...")
    for rel_data in backup_data["relationships"]["details"]:
        # Находим исходный узел
        source_query = """
        MATCH (n)
        WHERE n.name = $name AND $label IN labels(n)
        RETURN n LIMIT 1
        """
        source_label = rel_data["source_labels"][0]
        source_node = graph.evaluate(source_query, name=rel_data["source_name"], label=source_label)
        
        # Находим целевой узел
        target_query = """
        MATCH (n)
        WHERE n.name = $name AND $label IN labels(n)
        RETURN n LIMIT 1
        """
        target_label = rel_data["target_labels"][0]
        target_node = graph.evaluate(target_query, name=rel_data["target_name"], label=target_label)
        
        # Создаем связь, если оба узла найдены
        if source_node and target_node:
            rel_type = rel_data["relationship_type"]
            description = rel_data.get("description", "")
            rel = Relationship(source_node, rel_type, target_node, description=description)
            graph.create(rel)
    
    print(f"Восстановлено {len(backup_data['relationships']['details'])} связей")
    print(f"Восстановление из резервной копии успешно завершено")
    return True

def list_backups(backup_dir=None):
    """Выводит список доступных резервных копий"""
    if backup_dir is None:
        backup_dir = "backups"
    
    if not os.path.exists(backup_dir):
        print(f"Директория с резервными копиями не найдена: {backup_dir}")
        return False
    
    backup_files = [f for f in os.listdir(backup_dir) if f.startswith("neo4j_backup_") and f.endswith(".json")]
    
    if not backup_files:
        print(f"Резервные копии не найдены в директории: {backup_dir}")
        return False
    
    print(f"Доступные резервные копии ({len(backup_files)}):")
    for i, backup_file in enumerate(sorted(backup_files, reverse=True)):
        # Получаем дату создания из имени файла
        try:
            timestamp = backup_file.replace("neo4j_backup_", "").replace(".json", "")
            date_str = f"{timestamp[6:8]}.{timestamp[4:6]}.{timestamp[0:4]} {timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
        except:
            date_str = "Некорректный формат"
        
        # Получаем размер файла
        file_path = os.path.join(backup_dir, backup_file)
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # в МБ
        
        # Выводим информацию
        print(f"{i+1}. {backup_file}")
        print(f"   Дата: {date_str}")
        print(f"   Размер: {file_size:.2f} МБ")
        
        # Если есть информация о содержимом резервной копии, выводим её
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
                courses_count = len(backup_data["nodes"]["courses"])
                chapters_count = len(backup_data["nodes"]["chapters"])
                concepts_count = len(backup_data["nodes"]["concepts"])
                relations_count = len(backup_data["relationships"]["details"])
                print(f"   Содержит: {courses_count} курсов, {chapters_count} глав, {concepts_count} понятий, {relations_count} связей")
        except:
            print("   Не удалось прочитать информацию о содержимом")
        
        print()
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Управление резервными копиями базы данных Neo4j")
    subparsers = parser.add_subparsers(dest="command", help="Команда для выполнения")
    
    # Команда backup
    backup_parser = subparsers.add_parser("backup", help="Создать резервную копию базы данных")
    backup_parser.add_argument("--output-dir", type=str, default="backups", help="Директория для сохранения резервной копии")
    
    # Команда restore
    restore_parser = subparsers.add_parser("restore", help="Восстановить базу данных из резервной копии")
    restore_parser.add_argument("--file", type=str, required=True, help="Путь к файлу резервной копии")
    
    # Команда list
    list_parser = subparsers.add_parser("list", help="Показать список доступных резервных копий")
    list_parser.add_argument("--dir", type=str, default="backups", help="Директория с резервными копиями")
    
    args = parser.parse_args()
    
    if args.command == "backup":
        backup_database(args.output_dir)
    elif args.command == "restore":
        restore_database(args.file)
    elif args.command == "list":
        list_backups(args.dir)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 