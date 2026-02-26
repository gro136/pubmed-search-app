import sqlite3
import pandas as pd
import os

DB_PATH = "knowledge_base.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS papers (
            pmid TEXT PRIMARY KEY,
            title TEXT,
            authors TEXT,
            journal TEXT,
            year TEXT,
            abstract TEXT,
            url TEXT,
            domain TEXT,
            disease_area TEXT,
            scfa_role TEXT,
            evidence_level TEXT,
            claim_summary TEXT,
            mechanism_tags TEXT,
            population TEXT,
            intervention TEXT,
            outcomes TEXT,
            original_title TEXT,
            original_abstract TEXT,
            pub_types TEXT,
            keywords TEXT
        )
    ''')
    conn.commit()
    conn.close()

def upsert_paper(paper):
    conn = get_connection()
    c = conn.cursor()
    
    # SQLite upsert (INSERT ON CONFLICT)
    # Requires SQLite 3.24.0+
    sql = '''
        INSERT INTO papers (
            pmid, title, authors, journal, year, abstract, url, 
            domain, disease_area, scfa_role, evidence_level, 
            claim_summary, mechanism_tags, population, intervention, outcomes,
            original_title, original_abstract, pub_types, keywords
        ) VALUES (
            :pmid, :title, :authors, :journal, :year, :abstract, :url,
            :domain, :disease_area, :scfa_role, :evidence_level,
            :claim_summary, :mechanism_tags, :population, :intervention, :outcomes,
            :original_title, :original_abstract, :pub_types, :keywords
        )
        ON CONFLICT(pmid) DO UPDATE SET
            title=excluded.title,
            authors=excluded.authors,
            journal=excluded.journal,
            year=excluded.year,
            abstract=excluded.abstract,
            url=excluded.url,
            domain=excluded.domain,
            disease_area=excluded.disease_area,
            scfa_role=excluded.scfa_role,
            evidence_level=excluded.evidence_level,
            claim_summary=excluded.claim_summary,
            mechanism_tags=excluded.mechanism_tags,
            population=excluded.population,
            intervention=excluded.intervention,
            outcomes=excluded.outcomes,
            original_title=excluded.original_title,
            original_abstract=excluded.original_abstract,
            pub_types=excluded.pub_types,
            keywords=excluded.keywords
    '''
    c.execute(sql, paper)
    conn.commit()
    conn.close()

def get_papers(filters=None):
    conn = get_connection()
    query = "SELECT * FROM papers WHERE 1=1"
    params = []
    
    if filters:
        if filters.get('keyword'):
            kw = f"%{filters['keyword']}%"
            query += " AND (title LIKE ? OR abstract LIKE ? OR original_title LIKE ? OR original_abstract LIKE ?)"
            params.extend([kw, kw, kw, kw])
        if filters.get('disease_area') and filters['disease_area'] != "All":
            query += " AND disease_area = ?"
            params.append(filters['disease_area'])
        if filters.get('evidence_level') and filters['evidence_level'] != "All":
            query += " AND evidence_level = ?"
            params.append(filters['evidence_level'])
        if filters.get('year') and filters['year'] != "All":
            query += " AND year = ?"
            params.append(filters['year'])
            
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def delete_papers(pmids):
    if not pmids:
        return
        
    conn = get_connection()
    c = conn.cursor()
    
    # Create parameter placeholders based on list size
    placeholders = ','.join(['?'] * len(pmids))
    sql = f"DELETE FROM papers WHERE pmid IN ({placeholders})"
    
    c.execute(sql, pmids)
    conn.commit()
    conn.close()
