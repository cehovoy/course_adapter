#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import time
from py2neo import Graph as Neo4jGraph, Node, Relationship
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
    """Экспорт данных из Neo4j"""
    try:
        neo4j = Neo4jGraph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print(f"Соединение с Neo4j установлено: {NEO4J_URI}")
    except Exception as e:
        print(f"Ошибка подключения к Neo4j: {str(e)}")
        return None
    
    # Получаем все курсы
    courses = neo4j.run("""
        MATCH (c:Course)
        RETURN c
    """).data()
    print(f"Найдено {len(courses)} курсов")
    
    # Получаем все главы
    chapters = neo4j.run("""
        MATCH (ch:Chapter)
        RETURN ch
    """).data()
    print(f"Найдено {len(chapters)} глав")
    
    # Получаем все понятия
    concepts = neo4j.run("""
        MATCH (c:Concept)
        RETURN c
    """).data()
    print(f"Найдено {len(concepts)} понятий")
    
    # Получаем все связи
    relationships = neo4j.run("""
        MATCH (n1)-[r]->(n2)
        RETURN id(n1) AS source_id, n1.name AS source_name, labels(n1) AS source_labels,
               id(n2) AS target_id, n2.name AS target_name, labels(n2) AS target_labels,
               type(r) AS relationship_type, r.description AS description
    """).data()
    print(f"Найдено {len(relationships)} связей")
    
    return {
        "courses": courses,
        "chapters": chapters,
        "concepts": concepts,
        "relationships": relationships
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
    if not db.has_collection("relationships"):
        db.create_collection("relationships", edge=True)
        print("Создана коллекция связей: relationships")
    
    return db

def import_to_arango(neo4j_data):
    """Импорт данных в ArangoDB"""
    # Настраиваем ArangoDB
    db = setup_arango()
    
    # Получаем коллекции
    courses_collection = db.collection("courses")
    chapters_collection = db.collection("chapters")
    concepts_collection = db.collection("concepts")
    relationships_collection = db.collection("relationships")
    
    # Очищаем коллекции перед импортом
    courses_collection.truncate()
    chapters_collection.truncate()
    concepts_collection.truncate()
    relationships_collection.truncate()
    
    # Справочник Neo4j ID -> ArangoDB Key для связывания отношений
    id_mapping = {}
    
    # Импортируем курсы
    print("Импорт курсов...")
    for course_data in neo4j_data["courses"]:
        course = course_data["c"]
        
        # Создаем документ в ArangoDB
        document = {
            "_key": f"course_{course.get('name', 'unknown').replace(' ', '_')}",
            "name": course.get("name", ""),
            "description": course.get("description", ""),
            "neo4j_id": course.id,  # Сохраняем Neo4j ID для связывания
            "node_type": "Course"
        }
        
        # Вставляем документ
        meta = courses_collection.insert(document)
        
        # Сохраняем соответствие Neo4j ID -> ArangoDB Key
        id_mapping[course.id] = meta["_id"]
    
    # Импортируем главы
    print("Импорт глав...")
    for chapter_data in neo4j_data["chapters"]:
        chapter = chapter_data["ch"]
        
        # Создаем документ в ArangoDB
        document = {
            "_key": f"chapter_{chapter.get('title', 'unknown').replace(' ', '_')}",
            "title": chapter.get("title", ""),
            "description": chapter.get("description", ""),
            "course": chapter.get("course", ""),
            "neo4j_id": chapter.id,
            "node_type": "Chapter"
        }
        
        # Вставляем документ
        meta = chapters_collection.insert(document)
        
        # Сохраняем соответствие Neo4j ID -> ArangoDB Key
        id_mapping[chapter.id] = meta["_id"]
    
    # Импортируем понятия
    print("Импорт понятий...")
    for i, concept_data in enumerate(neo4j_data["concepts"]):
        concept = concept_data["c"]
        
        # Создаем уникальный ключ
        concept_key = f"concept_{concept.get('name', f'unknown_{i}').replace(' ', '_').replace('-', '_')}"
        
        # Ограничиваем длину ключа
        if len(concept_key) > 100:
            concept_key = concept_key[:100]
        
        # Создаем документ в ArangoDB
        document = {
            "_key": concept_key,
            "name": concept.get("name", ""),
            "definition": concept.get("definition", ""),
            "example": concept.get("example", ""),
            "questions": concept.get("questions", []),
            "neo4j_id": concept.id,
            "node_type": "Concept"
        }
        
        # Вставляем документ
        try:
            meta = concepts_collection.insert(document)
            # Сохраняем соответствие Neo4j ID -> ArangoDB Key
            id_mapping[concept.id] = meta["_id"]
        except Exception as e:
            print(f"Ошибка при вставке понятия {concept.get('name')}: {str(e)}")
            # Пробуем с автоматически сгенерированным ключом
            document.pop("_key", None)
            meta = concepts_collection.insert(document)
            id_mapping[concept.id] = meta["_id"]
    
    # Импортируем связи
    print("Импорт связей...")
    for i, rel in enumerate(neo4j_data["relationships"]):
        # Получаем ArangoDB ID для исходного и целевого узлов
        source_id = id_mapping.get(rel["source_id"])
        target_id = id_mapping.get(rel["target_id"])
        
        if source_id and target_id:
            # Создаем документ связи
            edge = {
                "_from": source_id,
                "_to": target_id,
                "type": rel["relationship_type"],
                "description": rel.get("description", ""),
                "source_name": rel.get("source_name", ""),
                "target_name": rel.get("target_name", "")
            }
            
            # Вставляем связь
            try:
                relationships_collection.insert(edge)
            except Exception as e:
                print(f"Ошибка при вставке связи {i}: {str(e)}")
    
    print("Импорт завершен!")
    
    # Возвращаем статистику
    return {
        "courses": courses_collection.count(),
        "chapters": chapters_collection.count(),
        "concepts": concepts_collection.count(),
        "relationships": relationships_collection.count()
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
        print(f"Связи: {stats['relationships']}")
        
        print("\nДанные успешно перенесены из Neo4j в ArangoDB.")
        print(f"Веб-интерфейс ArangoDB доступен по адресу: {ARANGO_HOST}")
    else:
        print("Ошибка при экспорте данных из Neo4j.")

if __name__ == "__main__":
    main() 