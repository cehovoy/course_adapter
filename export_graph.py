#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import argparse
from py2neo import Graph
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")
RESULTS_DIR = os.getenv("RESULTS_DIR", "results")

def ensure_results_dir():
    """Убедитесь, что директория для результатов существует"""
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
        print(f"Создана директория {RESULTS_DIR} для сохранения результатов")

def export_knowledge_graph(course_name=None):
    """Экспортирует весь граф знаний или граф конкретного курса в JSON-файл"""
    try:
        ensure_results_dir()
        
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        if course_name:
            # Запрос для экспорта знаний конкретного курса
            cypher_query = """
            MATCH (c:Course {name: $course_name})
            OPTIONAL MATCH (c)<-[r1:PART_OF]-(n)
            OPTIONAL MATCH (n)-[r2]-(m)
            WHERE (n:Chapter OR n:Concept) AND (m:Chapter OR m:Concept)
            RETURN c, r1, n, r2, m
            """
            print(f"Экспорт графа знаний для курса '{course_name}'...")
            result = graph.run(cypher_query, course_name=course_name).data()
            export_filename = f"course_{course_name.lower().replace(' ', '_')}_graph_export.json"
        else:
            # Запрос для экспорта всего графа знаний
            cypher_query = """
            MATCH (n)
            OPTIONAL MATCH (n)-[r]-(m)
            RETURN n, r, m
            """
            print("Экспорт всего графа знаний...")
            result = graph.run(cypher_query).data()
            export_filename = "complete_graph_export.json"
        
        # Преобразование результатов в JSON
        export_data = {
            "nodes": [],
            "relationships": []
        }
        
        # Словарь для отслеживания уже добавленных узлов
        processed_nodes = {}
        
        # Обработка результатов
        for record in result:
            # Обработка узлов
            for node_key in ['c', 'n', 'm']:
                if node_key in record and record[node_key] is not None:
                    node = record[node_key]
                    node_id = str(node.identity)
                    
                    if node_id not in processed_nodes:
                        # Добавляем узел в экспорт
                        node_data = {
                            "id": node_id,
                            "labels": list(node.labels),
                            "properties": dict(node)
                        }
                        export_data["nodes"].append(node_data)
                        processed_nodes[node_id] = True
            
            # Обработка отношений
            for rel_key in ['r1', 'r2']:
                if rel_key in record and record[rel_key] is not None:
                    rel = record[rel_key]
                    rel_data = {
                        "id": str(rel.identity),
                        "type": rel.type,
                        "startNode": str(rel.start_node.identity),
                        "endNode": str(rel.end_node.identity),
                        "properties": dict(rel)
                    }
                    export_data["relationships"].append(rel_data)
        
        # Сохранение в файл
        export_path = os.path.join(RESULTS_DIR, export_filename)
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        print(f"Граф знаний экспортирован в {export_path}")
        print(f"Всего экспортировано: {len(export_data['nodes'])} узлов, {len(export_data['relationships'])} связей")
        return True
    except Exception as e:
        print(f"Ошибка при экспорте графа знаний: {str(e)}")
        return False

def get_course_list():
    """Получает список всех курсов в базе данных"""
    try:
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Запрос для получения всех курсов
        cypher_query = "MATCH (c:Course) RETURN c.name AS name"
        result = graph.run(cypher_query).data()
        
        courses = [record["name"] for record in result]
        return courses
    except Exception as e:
        print(f"Ошибка при получении списка курсов: {str(e)}")
        return []

def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Экспорт графа знаний из Neo4j')
    parser.add_argument('--course', type=str, help='Название курса для экспорта (по умолчанию: все курсы)')
    parser.add_argument('--list', action='store_true', help='Вывести список всех курсов')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    if args.list:
        print("Список доступных курсов:")
        courses = get_course_list()
        for i, course in enumerate(courses):
            print(f"{i+1}. {course}")
    else:
        export_knowledge_graph(args.course) 