"""
TransitFlow — Neo4j Seeder
Run once after starting Docker:
    python skeleton/seed_neo4j.py

Loads station and network data from train-mock-data/:
  - metro_stations.json         — city metro stations and adjacencies
  - national_rail_stations.json — national rail stations and adjacencies
"""

import json
import os
import sys

sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)


def _load(filename):
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def seed():
    metro_stations = _load("metro_stations.json")
    rail_stations  = _load("national_rail_stations.json")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:

        session.run("MATCH (n) DETACH DELETE n")
        print("  Cleared existing graph data")

        # 1. Create Metro Station Nodes
        for st in metro_stations:
            session.run(
                """
                MERGE (m:Station:MetroStation {station_id: $id})
                SET m.name = $name,
                    m.lines = $lines,
                    m.is_interchange_national_rail = $is_interchange,
                    m.interchange_national_rail_station_id = $interchange_id
                """,
                id=st["station_id"],
                name=st["name"],
                lines=st.get("lines", []),
                is_interchange=st.get("is_interchange_national_rail", False),
                interchange_id=st.get("interchange_national_rail_station_id", "")
            )

        # 2. Create National Rail Station Nodes
        for st in rail_stations:
            session.run(
                """
                MERGE (r:Station:NationalRailStation {station_id: $id})
                SET r.name = $name,
                    r.lines = $lines,
                    r.is_interchange_metro = $is_interchange,
                    r.interchange_metro_station_id = $interchange_id
                """,
                id=st["station_id"],
                name=st["name"],
                lines=st.get("lines", []),
                is_interchange=st.get("is_interchange_metro", False),
                interchange_id=st.get("interchange_metro_station_id", "")
            )

        # 3. Create Metro Links
        for st in metro_stations:
            for adj in st.get("adjacent_stations", []):
                session.run(
                    """
                    MATCH (a:MetroStation {station_id: $from_id})
                    MATCH (b:MetroStation {station_id: $to_id})
                    MERGE (a)-[r:METRO_LINK {line: $line}]->(b)
                    SET r.travel_time_min = $time
                    """,
                    from_id=st["station_id"],
                    to_id=adj["station_id"],
                    line=adj.get("line", ""),
                    time=adj.get("travel_time_min", 0)
                )

        # 4. Create National Rail Links
        for st in rail_stations:
            for adj in st.get("adjacent_stations", []):
                session.run(
                    """
                    MATCH (a:NationalRailStation {station_id: $from_id})
                    MATCH (b:NationalRailStation {station_id: $to_id})
                    MERGE (a)-[r:RAIL_LINK {line: $line}]->(b)
                    SET r.travel_time_min = $time
                    """,
                    from_id=st["station_id"],
                    to_id=adj["station_id"],
                    line=adj.get("line", ""),
                    time=adj.get("travel_time_min", 0)
                )

        # 5. Create Interchange Links
        session.run(
            """
            MATCH (m:MetroStation)
            WHERE m.is_interchange_national_rail = true
            MATCH (r:NationalRailStation {station_id: m.interchange_national_rail_station_id})
            MERGE (m)-[rel1:INTERCHANGE_TO {travel_time_min: 5}]->(r)
            MERGE (r)-[rel2:INTERCHANGE_TO {travel_time_min: 5}]->(m)
            """
        )

    driver.close()
    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()
