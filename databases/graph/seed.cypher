// Deprecated: seeding is now done via skeleton/seed_neo4j.py
// which loads data directly from train-mock-data/ JSON files.
//
// If you prefer Cypher-file seeding, implement your graph schema here.
// Run with: python skeleton/seed_neo4j.py (or via the Neo4j Browser)

// ============================================================================
// TransitFlow — Neo4j Schema Setup & Topology Seed
// ============================================================================

// ────────────────────────────────────────────────────────────────────────────
// 1. SCHEMA CONSTRAINTS & INDEXES
// ────────────────────────────────────────────────────────────────────────────

// Ensure globally unique station IDs across all node varieties
CREATE CONSTRAINT station_id_unique IF NOT EXISTS
FOR (s:Station) REQUIRE s.station_id IS UNIQUE;

CREATE CONSTRAINT metro_id_unique IF NOT EXISTS
FOR (m:MetroStation) REQUIRE m.station_id IS UNIQUE;

CREATE CONSTRAINT rail_id_unique IF NOT EXISTS
FOR (r:RailStation) REQUIRE r.station_id IS UNIQUE;

// Index station names for speedy search engine and autocomplete matching
CREATE INDEX station_name_idx IF NOT EXISTS
FOR (s:Station) REQUIRE s.name IS TEXT;


// ────────────────────────────────────────────────────────────────────────────
// 2. METRO STATION TOPOLOGY NODES
// ────────────────────────────────────────────────────────────────────────────
CREATE (:Station:MetroStation {station_id: "MS01", name: "Central Square", lines: ["M1", "M2"]});
CREATE (:Station:MetroStation {station_id: "MS02", name: "Riverside", lines: ["M1"]});
CREATE (:Station:MetroStation {station_id: "MS03", name: "Westside Hub", lines: ["M1", "M3"]});
CREATE (:Station:MetroStation {station_id: "MS04", name: "Northpoint", lines: ["M1", "M4"]});
CREATE (:Station:MetroStation {station_id: "MS05", name: "Green Valley", lines: ["M1"]});
CREATE (:Station:MetroStation {station_id: "MS06", name: "Oakridge", lines: ["M2"]});
CREATE (:Station:MetroStation {station_id: "MS07", name: "Highland Park", lines: ["M2"]});
CREATE (:Station:MetroStation {station_id: "MS08", name: "East Gate", lines: ["M2", "M4"]});
CREATE (:Station:MetroStation {station_id: "MS09", name: "South Beach", lines: ["M3"]});
CREATE (:Station:MetroStation {station_id: "MS10", name: "Airport Terminal", lines: ["M3"]});
CREATE (:Station:MetroStation {station_id: "MS11", name: "Tech Park", lines: ["M3"]});
CREATE (:Station:MetroStation {station_id: "MS12", name: "Ocean View", lines: ["M3"]});
CREATE (:Station:MetroStation {station_id: "MS13", name: "Financial District", lines: ["M4"]});
CREATE (:Station:MetroStation {station_id: "MS14", name: "Stadium Complex", lines: ["M4"]});
CREATE (:Station:MetroStation {station_id: "MS15", name: "Grand Avenue", lines: ["M4"]});
CREATE (:Station:MetroStation {station_id: "MS16", name: "Harbor View", lines: ["M4"]});
CREATE (:Station:MetroStation {station_id: "MS17", name: "Summit Ridge", lines: ["M1", "M4"]});
CREATE (:Station:MetroStation {station_id: "MS18", name: "Sunnyvale", lines: ["M2"]});
CREATE (:Station:MetroStation {station_id: "MS19", name: "Redwood", lines: ["M3"]});


// ────────────────────────────────────────────────────────────────────────────
// 3. NATIONAL RAIL STATION TOPOLOGY NODES
// ────────────────────────────────────────────────────────────────────────────
CREATE (:Station:RailStation {station_id: "NR01", name: "Central Station", lines: ["NR1", "NR2"]});
CREATE (:Station:RailStation {station_id: "NR02", name: "Maplewood", lines: ["NR1"]});
CREATE (:Station:RailStation {station_id: "NR03", name: "Pinecrest", lines: ["NR1"]});
CREATE (:Station:RailStation {station_id: "NR04", name: "Oakwood", lines: ["NR1"]});
CREATE (:Station:RailStation {station_id: "NR05", name: "Silverton", lines: ["NR1"]});
CREATE (:Station:RailStation {station_id: "NR06", name: "Kingsbury", lines: ["NR2"]});
CREATE (:Station:RailStation {station_id: "NR07", name: "Grand Junction", lines: ["NR2"]});
CREATE (:Station:RailStation {station_id: "NR08", name: "Coalport", lines: ["NR2"]});
CREATE (:Station:RailStation {station_id: "NR09", name: "Dunmore", lines: ["NR2"]});


// ────────────────────────────────────────────────────────────────────────────
// 4. METRO TRACK SEGMENT LINKS (Bi-directional Network Adjacencies)
// ────────────────────────────────────────────────────────────────────────────
// Metro fares are standardized flat approximations based on distance/time ($0.50 per min)
MATCH (a:MetroStation {station_id: "MS01"}), (b:MetroStation {station_id: "MS02"}) MERGE (a)-[:LINK {line: "M1", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);
MATCH (a:MetroStation {station_id: "MS01"}), (b:MetroStation {station_id: "MS05"}) MERGE (a)-[:LINK {line: "M1", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);
MATCH (a:MetroStation {station_id: "MS01"}), (b:MetroStation {station_id: "MS06"}) MERGE (a)-[:LINK {line: "M2", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);
MATCH (a:MetroStation {station_id: "MS01"}), (b:MetroStation {station_id: "MS07"}) MERGE (a)-[:LINK {line: "M2", travel_time_min: 2, fare_standard_usd: 1.00, fare_first_usd: 1.00}]->(b);

MATCH (a:MetroStation {station_id: "MS03"}), (b:MetroStation {station_id: "MS02"}) MERGE (a)-[:LINK {line: "M1", travel_time_min: 4, fare_standard_usd: 2.00, fare_first_usd: 2.00}]->(b);
MATCH (a:MetroStation {station_id: "MS03"}), (b:MetroStation {station_id: "MS04"}) MERGE (a)-[:LINK {line: "M1", travel_time_min: 4, fare_standard_usd: 2.00, fare_first_usd: 2.00}]->(b);
MATCH (a:MetroStation {station_id: "MS03"}), (b:MetroStation {station_id: "MS09"}) MERGE (a)-[:LINK {line: "M3", travel_time_min: 5, fare_standard_usd: 2.50, fare_first_usd: 2.50}]->(b);
MATCH (a:MetroStation {station_id: "MS03"}), (b:MetroStation {station_id: "MS11"}) MERGE (a)-[:LINK {line: "M3", travel_time_min: 4, fare_standard_usd: 2.00, fare_first_usd: 2.00}]->(b);

MATCH (a:MetroStation {station_id: "MS04"}), (b:MetroStation {station_id: "MS17"}) MERGE (a)-[:LINK {line: "M1", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);
MATCH (a:MetroStation {station_id: "MS04"}), (b:MetroStation {station_id: "MS13"}) MERGE (a)-[:LINK {line: "M4", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);

MATCH (a:MetroStation {station_id: "MS05"}), (b:MetroStation {station_id: "MS17"}) MERGE (a)-[:LINK {line: "M1", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);
MATCH (a:MetroStation {station_id: "MS06"}), (b:MetroStation {station_id: "MS19"}) MERGE (a)-[:LINK {line: "M2", travel_time_min: 5, fare_standard_usd: 2.50, fare_first_usd: 2.50}]->(b);

MATCH (a:MetroStation {station_id: "MS08"}), (b:MetroStation {station_id: "MS07"}) MERGE (a)-[:LINK {line: "M2", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);
MATCH (a:MetroStation {station_id: "MS08"}), (b:MetroStation {station_id: "MS18"}) MERGE (a)-[:LINK {line: "M2", travel_time_min: 4, fare_standard_usd: 2.00, fare_first_usd: 2.00}]->(b);
MATCH (a:MetroStation {station_id: "MS08"}), (b:MetroStation {station_id: "MS14"}) MERGE (a)-[:LINK {line: "M4", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);
MATCH (a:MetroStation {station_id: "MS08"}), (b:MetroStation {station_id: "MS17"}) MERGE (a)-[:LINK {line: "M4", travel_time_min: 4, fare_standard_usd: 2.00, fare_first_usd: 2.00}]->(b);

MATCH (a:MetroStation {station_id: "MS10"}), (b:MetroStation {station_id: "MS09"}) MERGE (a)-[:LINK {line: "M3", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);
MATCH (a:MetroStation {station_id: "MS10"}), (b:MetroStation {station_id: "MS14"}) MERGE (a)-[:LINK {line: "M4", travel_time_min: 4, fare_standard_usd: 2.00, fare_first_usd: 2.00}]->(b);

MATCH (a:MetroStation {station_id: "MS12"}), (b:MetroStation {station_id: "MS11"}) MERGE (a)-[:LINK {line: "M3", travel_time_min: 4, fare_standard_usd: 2.00, fare_first_usd: 2.00}]->(b);
MATCH (a:MetroStation {station_id: "MS12"}), (b:MetroStation {station_id: "MS16"}) MERGE (a)-[:LINK {line: "M4", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);

MATCH (a:MetroStation {station_id: "MS13"}), (b:MetroStation {station_id: "MS15"}) MERGE (a)-[:LINK {line: "M4", travel_time_min: 4, fare_standard_usd: 2.00, fare_first_usd: 2.00}]->(b);
MATCH (a:MetroStation {station_id: "MS15"}), (b:MetroStation {station_id: "MS16"}) MERGE (a)-[:LINK {line: "M4", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);
MATCH (a:MetroStation {station_id: "MS18"}), (b:MetroStation {station_id: "MS19"}) MERGE (a)-[:LINK {line: "M2", travel_time_min: 3, fare_standard_usd: 1.50, fare_first_usd: 1.50}]->(b);


// ────────────────────────────────────────────────────────────────────────────
// 5. NATIONAL RAIL TRACK SEGMENT LINKS (Bi-directional Network Adjacencies)
// ────────────────────────────────────────────────────────────────────────────
// Rail links have higher travel times and support decoupled Standard ($0.80/m) and First ($1.50/m) class fares
MATCH (a:RailStation {station_id: "NR01"}), (b:RailStation {station_id: "NR02"}) MERGE (a)-[:LINK {line: "NR1", travel_time_min: 12, fare_standard_usd: 9.60, fare_first_usd: 18.00}]->(b);
MATCH (a:RailStation {station_id: "NR01"}), (b:RailStation {station_id: "NR06"}) MERGE (a)-[:LINK {line: "NR2", travel_time_min: 14, fare_standard_usd: 11.20, fare_first_usd: 21.00}]->(b);

MATCH (a:RailStation {station_id: "NR02"}), (b:RailStation {station_id: "NR03"}) MERGE (a)-[:LINK {line: "NR1", travel_time_min: 18, fare_standard_usd: 14.40, fare_first_usd: 27.00}]->(b);
MATCH (a:RailStation {station_id: "NR03"}), (b:RailStation {station_id: "NR04"}) MERGE (a)-[:LINK {line: "NR1", travel_time_min: 15, fare_standard_usd: 12.00, fare_first_usd: 22.50}]->(b);
MATCH (a:RailStation {station_id: "NR04"}), (b:RailStation {station_id: "NR05"}) MERGE (a)-[:LINK {line: "NR1", travel_time_min: 20, fare_standard_usd: 16.00, fare_first_usd: 30.00}]->(b);

MATCH (a:RailStation {station_id: "NR07"}), (b:RailStation {station_id: "NR06"}) MERGE (a)-[:LINK {line: "NR2", travel_time_min: 16, fare_standard_usd: 12.80, fare_first_usd: 24.00}]->(b);
MATCH (a:RailStation {station_id: "NR07"}), (b:RailStation {station_id: "NR08"}) MERGE (a)-[:LINK {line: "NR2", travel_time_min: 22, fare_standard_usd: 17.60, fare_first_usd: 33.00}]->(b);
MATCH (a:RailStation {station_id: "NR08"}), (b:RailStation {station_id: "NR09"}) MERGE (a)-[:LINK {line: "NR2", travel_time_min: 21, fare_standard_usd: 16.80, fare_first_usd: 31.50}]->(b);


// ────────────────────────────────────────────────────────────────────────────
// 6. CROSS-NETWORK INTERCHANGES (Multi-Modal Physical Transfers)
// ────────────────────────────────────────────────────────────────────────────
// Connect physical stations where platforms bridge Metro and National Rail networks
MATCH (m:MetroStation {station_id: "MS01"}), (r:RailStation {station_id: "NR01"})
MERGE (m)-[:INTERCHANGE {travel_time_min: 5, fare_standard_usd: 0.0, fare_first_usd: 0.0}]->(r)
MERGE (r)-[:INTERCHANGE {travel_time_min: 5, fare_standard_usd: 0.0, fare_first_usd: 0.0}]->(m);

MATCH (m:MetroStation {station_id: "MS15"}), (r:RailStation {station_id: "NR07"})
MERGE (m)-[:INTERCHANGE {travel_time_min: 5, fare_standard_usd: 0.0, fare_first_usd: 0.0}]->(r)
MERGE (r)-[:INTERCHANGE {travel_time_min: 5, fare_standard_usd: 0.0, fare_first_usd: 0.0}]->(m);