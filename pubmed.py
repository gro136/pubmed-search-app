import os
import ssl
os.environ['PYTHONHTTPSVERIFY'] = '0'
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

from Bio import Entrez

# Entrez requires an email
Entrez.email = "agent@example.com"

def fetch_pubmed_papers(query, start_year, start_month, end_year, end_month, free_full_text=False, pub_type="All", max_results=50, retstart=0):
    papers = []
    total_count = 0
    try:
        # Construct search query
        search_query = f"({query}[Title/Abstract])"
        if free_full_text:
            search_query += ' AND "free full text"[Filter]'
        if pub_type and pub_type != "All":
            search_query += f' AND "{pub_type}"[Publication Type]'
            
        mindate = f"{start_year}/{int(start_month):02d}/01"
        maxdate = f"{end_year}/{int(end_month):02d}/31"
        
        handle = Entrez.esearch(
            db="pubmed", 
            term=search_query, 
            mindate=mindate,
            maxdate=maxdate,
            datetype="pdat",
            retmax=max_results,
            retstart=retstart
        )
        record = Entrez.read(handle)
        handle.close()
        
        total_count = int(record.get("Count", "0"))
        
        id_list = record.get("IdList", [])
        if not id_list:
            return papers, total_count
            
        handle = Entrez.efetch(db="pubmed", id=id_list, retmode="xml")
        records = Entrez.read(handle)
        handle.close()
        
        for article in records.get('PubmedArticle', []):
            medline = article.get('MedlineCitation', {})
            article_data = medline.get('Article', {})
            
            pmid = str(medline.get('PMID', ''))
            title = article_data.get('ArticleTitle', '')
            
            # Authors
            author_list = article_data.get('AuthorList', [])
            authors = []
            for author in author_list:
                if 'LastName' in author and 'Initials' in author:
                    authors.append(f"{author['LastName']} {author['Initials']}")
            authors_str = ", ".join(authors) if authors else "Unknown"
            
            # Journal and Year
            journal = article_data.get('Journal', {}).get('Title', '')
            
            # PubDate extraction fallback
            pub_date = article_data.get('Journal', {}).get('JournalIssue', {}).get('PubDate', {})
            pub_year = pub_date.get('Year', start_year)
            
            # Abstract
            abstract_list = article_data.get('Abstract', {}).get('AbstractText', [])
            abstract_text = " ".join([str(text) for text in abstract_list]) if abstract_list else ""
            
            # Publication Types and Keywords
            pub_type_list = article_data.get('PublicationTypeList', [])
            original_pub_types = [str(pt) for pt in pub_type_list]
            
            keyword_lists = medline.get('KeywordList', [])
            original_keywords = []
            for kwlist in keyword_lists:
                original_keywords.extend([str(kw) for kw in kwlist])
            
            pub_types_str = ", ".join(original_pub_types)
            keywords_str = ", ".join(original_keywords)
            
            # Translation
            translated_title = title
            translated_abstract = abstract_text
            translated_pub_types = pub_types_str
            translated_keywords = keywords_str
            
            try:
                from deep_translator import GoogleTranslator
                translator = GoogleTranslator(source='auto', target='ko')
                if title:
                    translated_title = translator.translate(title)
                if abstract_text:
                    if len(abstract_text) > 4999: # Google Translator limit
                        translated_abstract = translator.translate(abstract_text[:4999]) + " ... (translated text truncated)"
                    else:
                        translated_abstract = translator.translate(abstract_text)
                if pub_types_str:
                    translated_pub_types = translator.translate(pub_types_str)
                if keywords_str:
                    translated_keywords = translator.translate(keywords_str)
            except Exception as tr_e:
                print(f"Translation failed: {tr_e}")
            
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            
            papers.append({
                "pmid": pmid,
                "title": f"{translated_title}\n(Original: {title})" if translated_title != title else title,
                "authors": authors_str,
                "journal": journal,
                "year": pub_year,
                "abstract": f"{translated_abstract}\n\n(Original)\n{abstract_text}" if translated_abstract != abstract_text and abstract_text else abstract_text,
                "url": url,
                "pub_types": translated_pub_types if translated_pub_types else pub_types_str,
                "keywords": translated_keywords if translated_keywords else keywords_str,
                "original_title": title,
                "original_abstract": abstract_text
            })
            
    except Exception as e:
        # Instead of breaking, we capture the exception to let Streamlit show it, but without crashing the server.
        raise RuntimeError(str(e))
        
    return papers, total_count

def dummy_classify_abstract(abstract):
    text = abstract.lower() if abstract else ""
    
    # Rule based dummy classifier
    disease_area = "알 수 없음"
    if "cancer" in text or "tumor" in text:
        disease_area = "종양학 (Oncology)"
    elif "gut" in text or "microbiome" in text or "ibd" in text:
        disease_area = "위장관학 (Gastroenterology)"
    elif "brain" in text or "alzheimer" in text or "parkinson" in text:
        disease_area = "신경학 (Neurology)"
    elif "immune" in text or "inflammation" in text:
        disease_area = "면역학 (Immunology)"
        
    evidence_level = "전임상 (Preclinical)"
    if "clinical trial" in text or "randomized" in text or "patients" in text:
        evidence_level = "임상시험 (Clinical Trial)"
    elif "meta-analysis" in text or "review" in text:
        evidence_level = "리뷰/메타분석 (Review/Meta-Analysis)"
        
    scfa_role = "중립적"
    if "increase" in text or "improve" in text or "beneficial" in text or "protect" in text:
        scfa_role = "보호적 (Protective)"
    elif "decrease" in text or "worsen" in text or "pathogenic" in text or "risk" in text:
        scfa_role = "유해함 (Harmful)"
        
    domain = "생명의학"
    mechanism_tags = "대사작용" if "metabol" in text else "일반"
    claim_summary = abstract[:120] + "..." if len(abstract) > 120 else abstract
    population = "인간" if "human" in text or "patients" in text or "clinical" in text else "마우스/세포"
    intervention = "약물/식이"
    outcomes = "개선됨" if scfa_role == "보호적 (Protective)" else "다양함"
    
    return {
        "domain": domain,
        "disease_area": disease_area,
        "scfa_role": scfa_role,
        "evidence_level": evidence_level,
        "claim_summary": claim_summary,
        "mechanism_tags": mechanism_tags,
        "population": population,
        "intervention": intervention,
        "outcomes": outcomes
    }
