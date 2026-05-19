"""
TransitFlow — Neo4j Seeder
Run once after starting Docker:
    python skeleton/seed_neo4j.py

Loads station and network data from train-mock-data/:
  - metro_stations.json         — city metro stations and adjacencies
  - national_rail_stations.json — national rail stations and adjacencies

Design your graph schema (node labels, relationship types, properties)
based on the data in these files, then implement the seed() function below.
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
        for station in metro_stations:
            session.run("""
                CREATE (s:Station:MetroStation {
                    station_id: $station_id,
                    name: $name,
                    lines: $lines
                })
            """, station_id=station["station_id"], name=station["name"], lines=station["lines"])
        print("  Created metro station nodes")

        # 2. Create National Rail Station Nodes
        for station in rail_stations:
            session.run("""
                CREATE (s:Station:RailStation {
                    station_id: $station_id,
                    name: $name,
                    lines: $lines
                })
            """, station_id=station["station_id"], name=station["name"], lines=station["lines"])
        print("  Created national rail station nodes")

        # 3. Create Metro Links (Bi-directional)
        for station in metro_stations:
            for adj in station["adjacent_stations"]:
                # Standardized pricing approximation: $0.50 per minute travel time
                fare_est = round(adj["travel_time_min"] * 0.50, 2)
                session.run("""
                    MATCH (a:MetroStation {station_id: $from_id}), (b:MetroStation {station_id: $to_id})
                    MERGE (a)-[r:LINK {line: $line}]->(b)
                    SET r.travel_time_min = $time,
                        r.fare_standard_usd = $fare,
                        r.fare_first_usd = $fare
                """, from_id=station["station_id"], to_id=adj["station_id"], 
                     line=adj["line"], time=adj["travel_time_min"], fare=fare_est)
        print("  Created metro links")

        # 4. Create National Rail Links (Bi-directional)
        for station in rail_stations:
            for adj in station["adjacent_stations"]:
                # Rail pricing approximation: Standard = $0.80/min, First Class = $1.50/min
                fare_std = round(adj["travel_time_min"] * 0.80, 2)
                fare_1st = round(adj["travel_time_min"] * 1.50, 2)
                session.run("""
                    MATCH (a:RailStation {station_id: $from_id}), (b:RailStation {station_id: $to_id})
                    MERGE (a)-[r:LINK {line: $line}]->(b)
                    SET r.travel_time_min = $time,
                        r.fare_standard_usd = $fare_std,
                        r.fare_first_usd = $fare_1st
                """, from_id=station["station_id"], to_id=adj["station_id"], 
                     line=adj["line"], time=adj["travel_time_min"], fare_std=fare_std, fare_1st=fare_1st)
        print("  Created national rail links")

        # 5. Create Cross-Network Interchange Relationships
        for station in metro_stations:
            if station["is_interchange_national_rail"] and station["interchange_national_rail_station_id"]:
                session.run("""
                    MATCH (m:MetroStation {station_id: $metro_id}), (r:RailStation {station_id: $rail_id})
                    MERGE (m)-[i:INTERCHANGE]->(r)
                    SET i.travel_time_min = 5, i.fare_standard_usd = 0.0, i.fare_first_usd = 0.0
                    MERGE (r)-[j:INTERCHANGE]->(m)
                    SET j.travel_time_min = 5, j.fare_standard_usd = 0.0, j.fare_first_usd = 0.0
                """, metro_id=station["station_id"], rail_id=station["interchange_national_rail_station_id"])
        print("  Created interchange relationships")

    driver.close()
    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()
