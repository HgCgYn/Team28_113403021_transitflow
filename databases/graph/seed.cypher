// TransitFlow — Neo4j Graph Seed (Cypher Reference)
// ====================================================
// NOTE: The live seeding pipeline uses skeleton/seed_neo4j.py, which loads
// station data directly from train-mock-data/ JSON files and runs MERGE-based
// Cypher programmatically.  This file documents the equivalent Cypher patterns
// for reference, study, and manual Neo4j Browser experimentation.
//
// Run via:  python skeleton/seed_neo4j.py
// Or paste individual statements into the Neo4j Browser at http://localhost:7475
//
// Relationship types used:
//   METRO_LINK       — directed link between two MetroStation nodes
//   RAIL_LINK        — directed link between two NationalRailStation nodes
//   INTERCHANGE_TO   — bidirectional link between a MetroStation and a NationalRailStation

// ── Verify the graph was loaded ───────────────────────────────────────────────
// Count all nodes and relationships:
//   MATCH (n) RETURN count(n) AS total_nodes;
//   MATCH ()-[r]->() RETURN count(r) AS total_relationships;

// ── Visualise the entire network ──────────────────────────────────────────────
//   MATCH (n)-[r]->(m) RETURN n, r, m

// ── Station nodes (MERGE pattern — idempotent) ────────────────────────────────

// Metro station example (line M1, Central Square):
MERGE (n:Station:MetroStation {station_id: "MS01"})
SET n.name = "Central Square",
    n.lines = ["M1", "M2"],
    n.is_interchange_national_rail = true,
    n.interchange_national_rail_station_id = "NR01";

// National Rail station example (line NR1, Central Station):
MERGE (n:Station:NationalRailStation {station_id: "NR01"})
SET n.name = "Central Station",
    n.lines = ["NR1"],
    n.is_interchange_metro = true,
    n.interchange_metro_station_id = "MS01";

// ── Relationship examples ─────────────────────────────────────────────────────

// Metro link (directed, with line and travel time):
// MATCH (a:MetroStation {station_id: "MS01"})
// MATCH (b:MetroStation {station_id: "MS02"})
// MERGE (a)-[r:METRO_LINK {line: "M1"}]->(b)
// SET r.travel_time_min = 3;

// National Rail link:
// MATCH (a:NationalRailStation {station_id: "NR01"})
// MATCH (b:NationalRailStation {station_id: "NR02"})
// MERGE (a)-[r:RAIL_LINK {line: "NR1"}]->(b)
// SET r.travel_time_min = 12;

// Cross-network interchange (auto-created by seed_neo4j.py for all interchange stations):
// MATCH (m:MetroStation {is_interchange_national_rail: true})
// MATCH (r:NationalRailStation {station_id: m.interchange_national_rail_station_id})
// MERGE (m)-[rel1:INTERCHANGE_TO {travel_time_min: 5}]->(r)
// MERGE (r)-[rel2:INTERCHANGE_TO {travel_time_min: 5}]->(m);

// ── Useful query examples (read-only) ─────────────────────────────────────────

// Fastest route from MS01 to MS14 (requires APOC):
// MATCH (start:Station {station_id: "MS01"})
// MATCH (end:Station {station_id: "MS14"})
// CALL apoc.algo.dijkstra(start, end, "METRO_LINK>", "travel_time_min") YIELD path, weight
// RETURN [n IN nodes(path) | n.name] AS stations, weight AS total_time_min;

// Alternative routes avoiding a disrupted station:
// MATCH p = (s:Station {station_id: "NR01"})-[:RAIL_LINK*1..10]->(e:Station {station_id: "NR05"})
// WHERE NONE(n IN nodes(p) WHERE n.station_id = "NR03")
// RETURN p, reduce(t=0, r IN relationships(p) | t + coalesce(r.travel_time_min, 0)) AS total_time
// ORDER BY total_time ASC LIMIT 3;

// Delay ripple — stations within 2 hops of a disruption:
// MATCH p = (s:Station {station_id: "NR03"})-[:METRO_LINK|RAIL_LINK*1..2]-(n:Station)
// WITH n, min(length(p)) AS hops
// RETURN n.station_id, n.name, hops ORDER BY hops;
