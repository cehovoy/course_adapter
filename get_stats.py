#!/usr/bin/env python
# -*- coding: utf-8 -*-

from py2neo import Graph
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Параметры подключения к Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

def get_course_stats():
    """Получает статистику по курсам в Neo4j"""
    try:
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        print("Статистика по курсам:")
        
        # Получаем список всех курсов
        courses = graph.run("MATCH (c:Course) RETURN c.name AS name").data()
        
        for course in courses:
            course_name = course["name"]
            
            # Общее количество понятий в курсе
            concepts = graph.run(
                "MATCH (c:Course {name: $name})<-[:PART_OF]-(concept:Concept) "
                "RETURN count(concept) AS count",
                name=course_name
            ).data()[0]["count"]
            
            # Количество понятий с определениями
            concepts_with_def = graph.run(
                "MATCH (c:Course {name: $name})<-[:PART_OF]-(concept:Concept) "
                "WHERE concept.definition IS NOT NULL AND concept.definition <> '' "
                "RETURN count(concept) AS count",
                name=course_name
            ).data()[0]["count"]
            
            # Количество связей между понятиями
            relationships = graph.run(
                "MATCH (c:Course {name: $name})<-[:PART_OF]-(c1:Concept)-[r]-(c2:Concept) "
                "WHERE c1 <> c2 RETURN count(r) AS count",
                name=course_name
            ).data()[0]["count"]
            
            # Статистика по типам связей
            rel_types = graph.run(
                "MATCH (c:Course {name: $name})<-[:PART_OF]-(c1:Concept)-[r]-(c2:Concept) "
                "WHERE c1 <> c2 RETURN type(r) AS type, count(r) AS count "
                "ORDER BY count DESC",
                name=course_name
            ).data()
            
            # Список понятий без определений
            concepts_without_def = graph.run(
                "MATCH (c:Course {name: $name})<-[:PART_OF]-(concept:Concept) "
                "WHERE concept.definition IS NULL OR concept.definition = '' "
                "RETURN concept.name AS name "
                "ORDER BY concept.name "
                "LIMIT 10",
                name=course_name
            ).data()
            
            # Вывод статистики
            print(f"\n{course_name}:")
            print(f"  Всего понятий: {concepts}")
            print(f"  Понятий с определениями: {concepts_with_def} ({round(concepts_with_def/concepts*100 if concepts > 0 else 0, 1)}%)")
            print(f"  Связей между понятиями: {relationships}")
            
            if rel_types:
                print("  Типы связей:")
                for rel in rel_types:
                    print(f"    {rel['type']}: {rel['count']}")
            
            if concepts_without_def:
                print("  Примеры понятий без определений (первые 10):")
                for concept in concepts_without_def:
                    print(f"    - {concept['name']}")
        
    except Exception as e:
        print(f"Ошибка при получении статистики: {str(e)}")

if __name__ == "__main__":
    get_course_stats() 