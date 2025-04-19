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
    """Восстанавливает базу данных из резервной копии, используя маппинг ID для связей."""
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
    
    # Создаем резервную копию текущей базы перед восстановлением (опционально, но рекомендуется)
    # print("Создание резервной копии текущей базы данных перед восстановлением...")
    # backup_before_restore = backup_database("backups/before_restore")
    
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
    created_nodes_count = 0
    # Восстанавливаем курсы
    for course_data in backup_data["nodes"]["courses"]:
        course_props = course_data["c"]
        course_node = Node("Course", **course_props)
        graph.create(course_node)
        created_nodes_count += 1
        # print(f"Восстановлен курс: {course_props.get('name', 'Без имени')}")
    
    # Восстанавливаем главы
    for chapter_data in backup_data["nodes"]["chapters"]:
        chapter_props = chapter_data["ch"]
        chapter_node = Node("Chapter", **chapter_props)
        graph.create(chapter_node)
        created_nodes_count += 1
        # print(f"Восстановлена глава: {chapter_props.get('title', 'Без названия')}") # Используем 'title' для глав, если есть
    
    # Восстанавливаем понятия
    concepts_count = 0
    for concept_data in backup_data["nodes"]["concepts"]:
        concept_props = concept_data["c"]
        concept_node = Node("Concept", **concept_props)
        graph.create(concept_node)
        created_nodes_count += 1
        concepts_count += 1
    
    print(f"Восстановлено узлов (Курсы, Главы, Понятия): {created_nodes_count}")
    print(f"Из них понятий: {concepts_count}")
    
    # --- Создание маппинга: original_id -> new_node_object ---
    print("Построение карты ID старых и новых узлов...")
    original_id_to_new_node = {}
    nodes_found_for_mapping = 0
    mapping_errors = 0
    
    # Собираем все уникальные ID из связей
    all_original_ids = set()
    for rel_data in backup_data["relationships"]["details"]:
        all_original_ids.add(rel_data["source_id"])
        all_original_ids.add(rel_data["target_id"])
    
    print(f"Найдено {len(all_original_ids)} уникальных ID узлов в связях бэкапа.")
    
    # Ищем новые узлы по имени/метке для каждого уникального ID
    # Используем данные из details, так как там есть и ID, и имя, и метки
    processed_ids_for_map = set()
    for rel_data in backup_data["relationships"]["details"]:
        # Обрабатываем source_id, если еще не обработан
        source_id = rel_data["source_id"]
        if source_id not in processed_ids_for_map:
            source_name = rel_data["source_name"]
            source_label = rel_data["source_labels"][0] if rel_data["source_labels"] else None
            if source_name and source_label:
                # Используем имя 'title' для глав, если метка Chapter
                name_prop = 'title' if source_label == 'Chapter' else 'name'
                query = f"MATCH (n:{source_label}) WHERE n.{name_prop} = $name RETURN n LIMIT 1"
                try:
                    # Используем graph.evaluate() который вернет один узел или None
                    node = graph.evaluate(query, name=source_name)
                    if node:
                        original_id_to_new_node[source_id] = node
                        nodes_found_for_mapping += 1
                    else:
                        print(f"Предупреждение: Не удалось найти новый узел для original_id {source_id} (Имя: '{source_name}', Метка: {source_label})")
                        mapping_errors += 1
                except Exception as e:
                    print(f"Ошибка при поиске узла для карты {source_id} (Имя: '{source_name}', Метка: {source_label}): {e}")
                    mapping_errors += 1
            processed_ids_for_map.add(source_id)
        
        # Обрабатываем target_id, если еще не обработан
        target_id = rel_data["target_id"]
        if target_id not in processed_ids_for_map:
            target_name = rel_data["target_name"]
            target_label = rel_data["target_labels"][0] if rel_data["target_labels"] else None
            if target_name and target_label:
                name_prop = 'title' if target_label == 'Chapter' else 'name'
                query = f"MATCH (n:{target_label}) WHERE n.{name_prop} = $name RETURN n LIMIT 1"
                try:
                    node = graph.evaluate(query, name=target_name)
                    if node:
                        original_id_to_new_node[target_id] = node
                        # Не увеличиваем nodes_found_for_mapping здесь, чтобы считать уникальные узлы
                    else:
                        print(f"Предупреждение: Не удалось найти новый узел для original_id {target_id} (Имя: '{target_name}', Метка: {target_label})")
                        mapping_errors += 1
                except Exception as e:
                    print(f"Ошибка при поиске узла для карты {target_id} (Имя: '{target_name}', Метка: {target_label}): {e}")
                    mapping_errors += 1
            processed_ids_for_map.add(target_id)
    
    print(f"Завершено построение карты: Найдено {len(original_id_to_new_node)} узлов из {len(all_original_ids)}. Ошибок/ненайденных: {mapping_errors}")
    if mapping_errors > 0:
        print("ПРЕДУПРЕЖДЕНИЕ: Не все узлы из связей бэкапа были найдены в новой базе. Некоторые связи могут быть не восстановлены.")
    
    # Восстанавливаем связи, используя маппинг ID
    print("Восстановление связей...")
    rels_created_count = 0
    rels_skipped_count = 0
    for rel_data in backup_data["relationships"]["details"]:
        source_id = rel_data["source_id"]
        target_id = rel_data["target_id"]
        
        # Получаем новые узлы из карты
        source_node = original_id_to_new_node.get(source_id)
        target_node = original_id_to_new_node.get(target_id)
        
        # Создаем связь, если оба узла были найдены в карте
        if source_node and target_node:
            rel_type = rel_data["relationship_type"]
            # Убедимся, что description существует, иначе пустая строка
            properties = {"description": rel_data.get("description", "")}
            # Добавим другие свойства связи, если они есть в бэкапе
            # for key, value in rel_data.items():
            #     if key not in ["source_id", "source_name", "source_labels",
            #                     "target_id", "target_name", "target_labels",
            #                     "relationship_type", "description"]:
            #         properties[key] = value
            
            rel = Relationship(source_node, rel_type, target_node, **properties)
            graph.create(rel)
            rels_created_count += 1
        else:
            rels_skipped_count += 1
            # print(f"Пропуск связи: не найден один или оба узла в карте для {source_id} -> {target_id}")
    
    print(f"Восстановлено связей: {rels_created_count}")
    if rels_skipped_count > 0:
        print(f"Пропущено связей из-за отсутствия узлов в карте: {rels_skipped_count}")
    
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