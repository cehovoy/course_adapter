#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
import re
from py2neo import Graph as Neo4jGraph
from arango import ArangoClient
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Параметры подключения к Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

# Параметры подключения к ArangoDB
ARANGO_HOST = os.getenv("ARANGO_HOST", "http://localhost:8529")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "12345678")
ARANGO_DB = os.getenv("ARANGO_DB", "adapter_course")

def export_from_neo4j():
    """Экспорт данных из Neo4j, но с другим подходом к запросам"""
    try:
        neo4j = Neo4jGraph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print(f"Соединение с Neo4j установлено: {NEO4J_URI}")
    except Exception as e:
        print(f"Ошибка подключения к Neo4j: {str(e)}")
        return None
    
    # Получаем все курсы с их свойствами
    courses = neo4j.run("""
        MATCH (c:Course)
        RETURN c.name as name, c.description as description
    """).data()
    print(f"Найдено {len(courses)} курсов")
    
    # Получаем все главы с их свойствами
    chapters = neo4j.run("""
        MATCH (ch:Chapter)
        RETURN ch.title as title, ch.description as description, ch.course as course
    """).data()
    print(f"Найдено {len(chapters)} глав")
    
    # Получаем все понятия с их свойствами
    concepts = neo4j.run("""
        MATCH (c:Concept)
        RETURN c.name as name, c.definition as definition, c.example as example, c.questions as questions
    """).data()
    print(f"Найдено {len(concepts)} понятий")
    
    # Получаем связи "глава - курс"
    chapter_course_rel = neo4j.run("""
        MATCH (ch:Chapter)-[r:PART_OF]->(c:Course)
        RETURN ch.title as chapter_title, c.name as course_name, type(r) as relationship_type, r.description as description
    """).data()
    print(f"Найдено {len(chapter_course_rel)} связей между главами и курсами")
    
    # Получаем связи "понятие - курс"
    concept_course_rel = neo4j.run("""
        MATCH (c:Concept)-[r:PART_OF]->(course:Course)
        RETURN c.name as concept_name, course.name as course_name, type(r) as relationship_type, r.description as description
    """).data()
    print(f"Найдено {len(concept_course_rel)} связей между понятиями и курсами")
    
    # Получаем связи "понятие - глава"
    concept_chapter_rel = neo4j.run("""
        MATCH (c:Concept)-[r:MENTIONED_IN]->(ch:Chapter)
        RETURN c.name as concept_name, ch.title as chapter_title, type(r) as relationship_type, r.description as description
    """).data()
    print(f"Найдено {len(concept_chapter_rel)} связей между понятиями и главами")
    
    # Получаем связи между понятиями
    concept_concept_rel = neo4j.run("""
        MATCH (c1:Concept)-[r]->(c2:Concept)
        RETURN c1.name as source_name, c2.name as target_name, type(r) as relationship_type, r.description as description
    """).data()
    print(f"Найдено {len(concept_concept_rel)} связей между понятиями")
    
    return {
        "courses": courses,
        "chapters": chapters,
        "concepts": concepts,
        "relationships": {
            "chapter_course": chapter_course_rel,
            "concept_course": concept_course_rel,
            "concept_chapter": concept_chapter_rel,
            "concept_concept": concept_concept_rel
        }
    }

def setup_arango():
    """Настройка и подключение к ArangoDB"""
    # Инициализация клиента
    client = ArangoClient(hosts=ARANGO_HOST)
    
    # Подключение к системной базе данных
    sys_db = client.db("_system", username=ARANGO_USER, password=ARANGO_PASSWORD)
    
    # Создаем базу данных, если она не существует
    if not sys_db.has_database(ARANGO_DB):
        sys_db.create_database(ARANGO_DB)
        print(f"Создана база данных: {ARANGO_DB}")
    
    # Подключение к базе данных
    db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASSWORD)
    
    # Создаем коллекции, если они не существуют
    if not db.has_collection("courses"):
        db.create_collection("courses")
        print("Создана коллекция: courses")
    
    if not db.has_collection("chapters"):
        db.create_collection("chapters")
        print("Создана коллекция: chapters")
    
    if not db.has_collection("concepts"):
        db.create_collection("concepts")
        print("Создана коллекция: concepts")
    
    # Создаем коллекцию ребер, если не существует
    if not db.has_collection("edges"):
        db.create_collection("edges", edge=True)
        print("Создана коллекция связей: edges")
    
    return db

def import_to_arango(neo4j_data):
    """Импорт данных в ArangoDB"""
    # Настраиваем ArangoDB
    db = setup_arango()
    
    # Получаем коллекции
    courses_collection = db.collection("courses")
    chapters_collection = db.collection("chapters")
    concepts_collection = db.collection("concepts")
    edges_collection = db.collection("edges")
    
    # Очищаем коллекции перед импортом
    courses_collection.truncate()
    chapters_collection.truncate()
    concepts_collection.truncate()
    edges_collection.truncate()
    
    # Импортируем курсы
    print("Импорт курсов...")
    for course in neo4j_data["courses"]:
        # Создаем ключ, удаляя все недопустимые символы
        course_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', course["name"])
        document = {
            "_key": course_key,
            "name": course["name"],
            "description": course.get("description", ""),
            "node_type": "Course"
        }
        courses_collection.insert(document)
    
    # Импортируем главы
    print("Импорт глав...")
    for chapter in neo4j_data["chapters"]:
        # Создаем ключ, удаляя все недопустимые символы
        chapter_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', chapter["title"])
        document = {
            "_key": chapter_key,
            "title": chapter["title"],
            "description": chapter.get("description", ""),
            "course": chapter.get("course", ""),
            "node_type": "Chapter"
        }
        try:
            chapters_collection.insert(document)
        except Exception as e:
            print(f"Ошибка при вставке главы {chapter['title']}: {str(e)}")
            # Пробуем с автоматическим ключом
            document.pop("_key", None)
            chapters_collection.insert(document)
    
    # Импортируем понятия
    print("Импорт понятий...")
    for concept in neo4j_data["concepts"]:
        # Создаем ключ, удаляя все недопустимые символы
        concept_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', concept["name"])
        if len(concept_key) > 100:
            concept_key = concept_key[:100]
        
        document = {
            "_key": concept_key,
            "name": concept["name"],
            "definition": concept.get("definition", ""),
            "example": concept.get("example", ""),
            "questions": concept.get("questions", []),
            "node_type": "Concept"
        }
        
        try:
            concepts_collection.insert(document)
        except Exception as e:
            print(f"Ошибка при вставке понятия {concept['name']}: {str(e)}")
            # Пропускаем ошибочные ключи и генерируем новые
            document.pop("_key", None)
            concepts_collection.insert(document)
    
    # Импортируем связи "глава - курс"
    print("Импорт связей между главами и курсами...")
    for rel in neo4j_data["relationships"]["chapter_course"]:
        try:
            chapter_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', rel["chapter_title"])
            course_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', rel["course_name"])
            
            edge = {
                "_from": f"chapters/{chapter_key}",
                "_to": f"courses/{course_key}",
                "type": rel["relationship_type"],
                "description": rel.get("description", "")
            }
            
            edges_collection.insert(edge)
        except Exception as e:
            print(f"Ошибка при вставке связи глава-курс: {str(e)}")
    
    # Импортируем связи "понятие - курс"
    print("Импорт связей между понятиями и курсами...")
    for rel in neo4j_data["relationships"]["concept_course"]:
        try:
            concept_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', rel["concept_name"])
            if len(concept_key) > 100:
                concept_key = concept_key[:100]
            
            course_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', rel["course_name"])
            
            edge = {
                "_from": f"concepts/{concept_key}",
                "_to": f"courses/{course_key}",
                "type": rel["relationship_type"],
                "description": rel.get("description", "")
            }
            
            edges_collection.insert(edge)
        except Exception as e:
            print(f"Ошибка при вставке связи понятие-курс: {str(e)}")
    
    # Импортируем связи "понятие - глава"
    print("Импорт связей между понятиями и главами...")
    for rel in neo4j_data["relationships"]["concept_chapter"]:
        try:
            concept_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', rel["concept_name"])
            if len(concept_key) > 100:
                concept_key = concept_key[:100]
            
            chapter_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', rel["chapter_title"])
            
            edge = {
                "_from": f"concepts/{concept_key}",
                "_to": f"chapters/{chapter_key}",
                "type": rel["relationship_type"],
                "description": rel.get("description", "")
            }
            
            edges_collection.insert(edge)
        except Exception as e:
            print(f"Ошибка при вставке связи понятие-глава: {str(e)}")
    
    # Импортируем связи между понятиями
    print("Импорт связей между понятиями...")
    successful_edges = 0
    failed_edges = 0
    
    for rel in neo4j_data["relationships"]["concept_concept"]:
        try:
            source_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', rel["source_name"])
            if len(source_key) > 100:
                source_key = source_key[:100]
            
            target_key = re.sub(r'[^a-zA-Z0-9_\-:]', '_', rel["target_name"])
            if len(target_key) > 100:
                target_key = target_key[:100]
            
            edge = {
                "_from": f"concepts/{source_key}",
                "_to": f"concepts/{target_key}",
                "type": rel["relationship_type"],
                "description": rel.get("description", ""),
                "source_name": rel["source_name"],
                "target_name": rel["target_name"]
            }
            
            edges_collection.insert(edge)
            successful_edges += 1
        except Exception as e:
            failed_edges += 1
            if failed_edges < 10:  # Ограничим количество выводимых ошибок
                print(f"Ошибка при вставке связи понятие-понятие: {str(e)}")
    
    print(f"Успешно импортировано {successful_edges} связей между понятиями")
    if failed_edges > 0:
        print(f"Не удалось импортировать {failed_edges} связей между понятиями")
    
    print("Импорт завершен!")
    
    # Возвращаем статистику
    return {
        "courses": courses_collection.count(),
        "chapters": chapters_collection.count(),
        "concepts": concepts_collection.count(),
        "edges": edges_collection.count()
    }

def main():
    print("Начало экспорта данных из Neo4j...")
    neo4j_data = export_from_neo4j()
    
    if neo4j_data:
        print("Экспорт из Neo4j завершен успешно.")
        
        print("\nНачало импорта данных в ArangoDB...")
        stats = import_to_arango(neo4j_data)
        
        print("\nИмпорт завершен! Статистика:")
        print(f"Курсы: {stats['courses']}")
        print(f"Главы: {stats['chapters']}")
        print(f"Понятия: {stats['concepts']}")
        print(f"Связи: {stats['edges']}")
        
        print("\nДанные успешно перенесены из Neo4j в ArangoDB.")
        print(f"Веб-интерфейс ArangoDB доступен по адресу: {ARANGO_HOST}")
    else:
        print("Ошибка при экспорте данных из Neo4j.")

if __name__ == "__main__":
    main() 