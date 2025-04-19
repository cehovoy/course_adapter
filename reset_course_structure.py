#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
from py2neo import Graph
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Параметры подключения
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

def reset_course_structure(course_name, delete_concepts=False, graph=None):
    """
    Сбрасывает структуру курса, удаляя главы, темы и связи.
    
    Parameters:
    - course_name: название курса
    - delete_concepts: если True, удаляет также понятия курса
    - graph: существующее подключение к Neo4j (опционально)
    """
    if graph is None:
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Получаем узел курса
    course_node = graph.nodes.match("Course", name=course_name).first()
    if not course_node:
        print(f"Ошибка: Курс '{course_name}' не найден")
        return False
    
    print(f"Сброс структуры курса '{course_name}'...")
    
    # Удаляем связи понятий с темами
    query_theme_rels = """
    MATCH (t:Theme {course: $course_name})<-[r:BELONGS_TO]-(c:Concept)
    DELETE r
    """
    result = graph.run(query_theme_rels, course_name=course_name)
    print(f"Удалены связи понятий с темами ({result.stats().get('relationships_deleted', 0)} связей)")
    
    # Удаляем темы
    query_themes = """
    MATCH (t:Theme {course: $course_name})
    DETACH DELETE t
    """
    result = graph.run(query_themes, course_name=course_name)
    print(f"Удалены темы ({result.stats().get('nodes_deleted', 0)} тем)")
    
    # Удаляем связи понятий с главами
    query_chapter_rels = """
    MATCH (ch:Chapter {course: $course_name})<-[r:MENTIONED_IN]-(c:Concept)
    DELETE r
    """
    result = graph.run(query_chapter_rels, course_name=course_name)
    print(f"Удалены связи понятий с главами ({result.stats().get('relationships_deleted', 0)} связей)")
    
    # Удаляем главы
    query_chapters = """
    MATCH (ch:Chapter {course: $course_name})
    DETACH DELETE ch
    """
    result = graph.run(query_chapters, course_name=course_name)
    print(f"Удалены главы ({result.stats().get('nodes_deleted', 0)} глав)")
    
    if delete_concepts:
        # Удаляем связи между понятиями
        query_concept_rels = """
        MATCH (c1:Concept)-[r]-(c2:Concept)
        WHERE (c1)-[:PART_OF]->({name: $course_name}) AND (c2)-[:PART_OF]->({name: $course_name})
        DELETE r
        """
        result = graph.run(query_concept_rels, course_name=course_name)
        print(f"Удалены связи между понятиями ({result.stats().get('relationships_deleted', 0)} связей)")
        
        # Удаляем понятия
        query_concepts = """
        MATCH (c:Concept)-[:PART_OF]->(course:Course {name: $course_name})
        DETACH DELETE c
        """
        result = graph.run(query_concepts, course_name=course_name)
        print(f"Удалены понятия ({result.stats().get('nodes_deleted', 0)} понятий)")
    
    print(f"Структура курса '{course_name}' успешно сброшена")
    return True

def main():
    parser = argparse.ArgumentParser(description="Сброс структуры курса в Neo4j")
    parser.add_argument("--course", type=str, required=True, help="Название курса")
    parser.add_argument("--delete-concepts", action="store_true", help="Удалить также понятия курса")
    args = parser.parse_args()
    
    reset_course_structure(args.course, args.delete_concepts)
    
    if args.delete_concepts:
        print(f"Курс '{args.course}' полностью очищен (включая понятия)")
    else:
        print(f"Структура курса '{args.course}' сброшена (понятия сохранены)")

if __name__ == "__main__":
    main() 