from __future__ import annotations
from typing import Optional
from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def _driver():
    """Return a Neo4j driver. Caller is responsible for closing."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def example_count_nodes() -> int:
    """Example: count all nodes currently in the graph."""
    with _driver() as driver:
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            return result.single()["total"]


# ── FASTEST ROUTE (Dijkstra by travel_time_min) ───────────────────────────────

def query_shortest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
) -> dict:
    """
    Find the fastest path between two stations, minimising total travel time.
    Uses apoc.algo.dijkstra for optimized property weight traversal.
    """
    # Determine fallback target nodes if network explicitly specified
    label_filter = "Station"
    if network == "metro":
        label_filter = "MetroStation"
    elif network == "rail":
        label_filter = "RailStation"

    cypher_query = f"""
    MATCH (start:{label_filter} {{station_id: $origin_id}}), (end:{label_filter} {{station_id: $destination_id}})
    CALL apoc.algo.dijkstra(start, end, 'LINK|INTERCHANGE', 'travel_time_min') YIELD path, weight
    RETURN weight as total_time, 
           [n IN nodes(path) | {{station_id: n.station_id, name: n.name, lines: n.lines}}] as stations,
           [r IN relationships(path) | {{line: coalesce(r.line, 'Interchange'), travel_time_min: r.travel_time_min}}] as legs
    """
    
    with _driver() as driver:
        with driver.session() as session:
            result = session.run(cypher_query, origin_id=origin_id, destination_id=destination_id)
            record = result.single()
            if not record:
                return {"found": False, "origin_id": origin_id, "destination_id": destination_id, "total_time_min": 0, "path": [], "legs": []}
            
            return {
                "found": True,
                "origin_id": origin_id,
                "destination_id": destination_id,
                "total_time_min": record["total_time"],
                "path": record["stations"],
                "legs": record["legs"]
            }


# ── CHEAPEST ROUTE (Dijkstra by fare) ────────────────────────────────────────

def query_cheapest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
    fare_class: str = "standard",
) -> dict:
    """
    Find the cheapest path between two stations, minimising total estimated fare.
    """
    fare_property = "fare_first_usd" if fare_class == "first" else "fare_standard_usd"
    label_filter = "Station"
    if network == "metro":
        label_filter = "MetroStation"
    elif network == "rail":
        label_filter = "RailStation"

    cypher_query = f"""
    MATCH (start:{label_filter} {{station_id: $origin_id}}), (end:{label_filter} {{station_id: $destination_id}})
    CALL apoc.algo.dijkstra(start, end, 'LINK|INTERCHANGE', '{fare_property}') YIELD path, weight
    RETURN weight as total_fare, 
           [n IN nodes(path) | {{station_id: n.station_id, name: n.name}}] as stations,
           [r IN relationships(path) | {{line: coalesce(r.line, 'Interchange'), fare: r.{fare_property}}}] as legs
    """
    
    with _driver() as driver:
        with driver.session() as session:
            result = session.run(cypher_query, origin_id=origin_id, destination_id=destination_id)
            record = result.single()
            if not record:
                return {"found": False, "total_fare_usd": 0.0, "stations": [], "legs": []}
            
            return {
                "found": True,
                "total_fare_usd": round(record["total_fare"], 2),
                "stations": record["stations"],
                "legs": record["legs"]
            }


# ── ALTERNATIVE ROUTES (avoiding a station) ───────────────────────────────────

def query_alternative_routes(
    origin_id: str,
    destination_id: str,
    avoid_station_id: str,
    network: str = "auto",
    max_routes: int = 3,
) -> list[list[dict]]:
    """
    Find paths between two stations that completely circumvent a specific intermediate station.
    """
    label_filter = "Station"
    if network == "metro":
        label_filter = "MetroStation"
    elif network == "rail":
        label_filter = "RailStation"

    # Fetching alternative paths using allShortestPaths or simple path matches, filtered via avoiding node.
    cypher_query = f"""
    MATCH path = (start:{label_filter} {{station_id: $origin_id}})-[:LINK|INTERCHANGE*..15]->(end:{label_filter} {{station_id: $destination_id}})
    WHERE NONE(n IN nodes(path) WHERE n.station_id = $avoid_station_id)
    RETURN [r IN relationships(path) | {{
        from: startNode(r).station_id, 
        to: endNode(r).station_id, 
        line: coalesce(r.line, 'Interchange'), 
        travel_time_min: r.travel_time_min
    }}] as legs
    ORDER BY reduce(acc = 0, r IN relationships(path) | acc + r.travel_time_min) ASC
    LIMIT $max_routes
    """
    
    with _driver() as driver:
        with driver.session() as session:
            result = session.run(cypher_query, origin_id=origin_id, destination_id=destination_id, avoid_station_id=avoid_station_id, max_routes=max_routes)
            return [record["legs"] for record in result]


# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:
    """
    Find paths explicitly crossing transit network boundaries via INTERCHANGE links.
    """
    cypher_query = """
    MATCH (start:Station {station_id: $origin_id}), (end:Station {station_id: $destination_id})
    CALL apoc.algo.dijkstra(start, end, 'LINK|INTERCHANGE', 'travel_time_min') YIELD path, weight
    WITH path, weight, [r IN relationships(path) WHERE type(r) = 'INTERCHANGE'] as interchanges
    RETURN weight as total_time,
           [n IN nodes(path) | {station_id: n.station_id, name: n.name}] as stations,
           [i IN interchanges | {from_station: startNode(i).station_id, to_station: endNode(i).station_id}] as interchange_points
    """
    
    with _driver() as driver:
        with driver.session() as session:
            result = session.run(cypher_query, origin_id=origin_id, destination_id=destination_id)
            record = result.single()
            if not record:
                return {"found": False, "stations": [], "interchange_points": [], "total_time_min": 0}
            
            return {
                "found": True,
                "stations": record["stations"],
                "interchange_points": record["interchange_points"],
                "total_time_min": record["total_time"]
            }


# ── DELAY RIPPLE ANALYSIS ─────────────────────────────────────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:
    """
    Find all stations within N hops of a delayed station and identify what lines are impacted.
    """
    cypher_query = """
    MATCH path = (start:Station {station_id: $delayed_station_id})-[:LINK*..%d]->(affected:Station)
    WHERE start <> affected
    WITH affected, min(length(path)) as hops_away, apoc.coll.flatten(collect([r IN relationships(path) | r.line])) as raw_lines
    UNWIND raw_lines as line
    WITH affected, hops_away, collect(DISTINCT line) as lines_affected
    RETURN affected.station_id as station_id, affected.name as name, hops_away, lines_affected
    ORDER BY hops_away ASC, station_id ASC
    """ % hops

    with _driver() as driver:
        with driver.session() as session:
            result = session.run(cypher_query, delayed_station_id=delayed_station_id)
            return [dict(record) for record in result]


# ── STATION CONNECTIONS ───────────────────────────────────────────────────────

def query_station_connections(station_id: str) -> list[dict]:
    """
    List all direct adjacent connections and metadata from a given target station.
    """
    cypher_query = """
    MATCH (start:Station {station_id: $station_id})-[r:LINK]->(neighbor:Station)
    RETURN neighbor.station_id as station_id, 
           neighbor.name as name, 
           r.line as line, 
           r.travel_time_min as travel_time_min,
           r.fare_standard_usd as fare_standard_usd
    ORDER BY line ASC, station_id ASC
    """
    with _driver() as driver:
        with driver.session() as session:
            result = session.run(cypher_query, station_id=station_id)
            return [dict(record) for record in result]
