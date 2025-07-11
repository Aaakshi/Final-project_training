CREATE DATABASE idcr_db;
\c idcr_db

CREATE TABLE documents (
    doc_id UUID PRIMARY KEY,
    original_name VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,
    doc_type VARCHAR(50),
    confidence FLOAT
);

CREATE TABLE metadata (
    meta_id SERIAL PRIMARY KEY,
    doc_id UUID NOT NULL REFERENCES documents(doc_id),
    key_entities JSONB,
    related_docs UUID[],
    risk_score FLOAT
);

CREATE TABLE routing_rules (
    rule_id SERIAL PRIMARY KEY,
    condition JSONB,
    assignee VARCHAR(100),
    priority INT
);