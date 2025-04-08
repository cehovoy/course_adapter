#!/usr/bin/env python
# -*- coding: utf-8 -*-

from py2neo import Graph, Node, Relationship
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация подключения к Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

def clean_neo4j():
    """Очищает базу данных Neo4j и создаёт корневую структуру для курсов"""
    try:
        # Подключение к Neo4j
        graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Удаление всех данных из базы
        print("Удаление всех узлов и связей...")
        graph.run("MATCH (n) DETACH DELETE n")
        
        # Создание корневого узла верхнего уровня
        print("Создание корневого узла 'Курсы саморазвития'...")
        root_node = Node("CourseRoot", name="Курсы саморазвития", description="Корневой узел для всех курсов по саморазвитию")
        graph.create(root_node)
        
        # Создание узла для первого курса
        print("Создание узла для курса 'Системное саморазвитие'...")
        course1_node = Node("Course", name="Системное саморазвитие", description="Курс по системному саморазвитию")
        graph.create(course1_node)
        
        # Создание узла для второго курса
        print("Создание узла для курса 'Практики саморазвития'...")
        course2_node = Node("Course", name="Практики саморазвития", description="Курс по практикам саморазвития")
        graph.create(course2_node)
        
        # Создание связей между курсами и корневым узлом
        rel1 = Relationship(course1_node, "PART_OF", root_node, description="Курс 'Системное саморазвитие' является частью программы по саморазвитию")
        rel2 = Relationship(course2_node, "PART_OF", root_node, description="Курс 'Практики саморазвития' является частью программы по саморазвитию")
        graph.create(rel1)
        graph.create(rel2)
        
        print("База данных Neo4j успешно очищена и подготовлена для работы")
        print(f"URI для подключения: {NEO4J_URI}")
        return True
    except Exception as e:
        print(f"Ошибка при очистке базы данных Neo4j: {str(e)}")
        return False

if __name__ == "__main__":
    clean_neo4j() 