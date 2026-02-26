import os
import ssl
os.environ['PYTHONHTTPSVERIFY'] = '0'
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

import streamlit as st
import pandas as pd
import io
import datetime
from database import init_db, upsert_paper, get_papers, delete_papers
from pubmed import fetch_pubmed_papers, dummy_classify_abstract

# Setup page
st.set_page_config(page_title="연구 지식 베이스", layout="wide", page_icon="📚")

# Initialize SQLite tables
init_db()

st.title("📚 나만의 연구 지식 베이스 (PubMed 검색 및 관리)")

tab1, tab2 = st.tabs(["🔍 논문 수집 및 저장", "📁 내 지식 서재 (활용/추출)"])

# ----------------- #
# Tab 1: Collection #
# ----------------- #
with tab1:
    st.header("PubMed 논문 검색")
    
    with st.expander("검색 상세 설정", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("검색 키워드 (예: SCFA)", value="")
            
            st.markdown("**출판 기간 설정**")
            current_year = datetime.datetime.now().year
            col_sy, col_sm = st.columns(2)
            with col_sy:
                start_year = st.number_input("시작 연도", value=current_year-5, min_value=1900, max_value=current_year)
            with col_sm:
                start_month = st.selectbox("시작 월", range(1, 13), index=0)
                
            col_ey, col_em = st.columns(2)
            with col_ey:
                end_year = st.number_input("종료 연도", value=current_year, min_value=1900, max_value=current_year)
            with col_em:
                end_month = st.selectbox("종료 월", range(1, 13), index=11)
                
        with col2:
            st.markdown("**필터 옵션**")
            free_full_text = st.checkbox("무료 원문만 보기 (Free full text)", value=False)
            pub_types_kr_to_en = {
                "전체": "All",
                "리뷰 논문": "Review",
                "임상 시험": "Clinical Trial",
                "메타 분석": "Meta-Analysis",
                "무작위 대조 시험": "Randomized Controlled Trial",
                "체계적 문헌 고찰": "Systematic Review"
            }
            pub_type_kr = st.selectbox("논문 종류 (Publication Type)", list(pub_types_kr_to_en.keys()))
            pub_type = pub_types_kr_to_en[pub_type_kr]
            
            st.markdown("**결과 표시 설정**")
            max_results = st.selectbox("한 번에 가져올 논문 개수", [10, 50, 100, 200], index=0)
            
    if st.button("논문 검색", type="primary"):
        if keyword.strip() == "":
            st.warning("키워드를 입력해주세요.")
        else:
            with st.spinner("논문 데이터를 가져오고 번역하는 중입니다. 잠시만 기다려주세요... ⏳"):
                try:
                    results, total_count = fetch_pubmed_papers(
                        keyword, start_year, start_month, end_year, end_month, 
                        free_full_text, pub_type, max_results, retstart=0
                    )
                    if not results:
                        st.warning("검색 결과가 없습니다.")
                        if 'search_results' in st.session_state:
                            del st.session_state['search_results']
                    else:
                        st.session_state['search_results'] = results
                        st.session_state['total_count'] = total_count
                        st.session_state['retstart'] = max_results
                        st.session_state['keyword'] = keyword
                        st.session_state['start_year'] = start_year
                        st.session_state['start_month'] = start_month
                        st.session_state['end_year'] = end_year
                        st.session_state['end_month'] = end_month
                        st.session_state['free_full_text'] = free_full_text
                        st.session_state['pub_type'] = pub_type
                        st.session_state['max_results'] = max_results
                        st.session_state.select_all = False
                        st.session_state.editor_key = st.session_state.get('editor_key', 0) + 1
                except Exception as e:
                    st.error(f"PubMed API 오류가 발생했습니다: {e}")
                
    if 'search_results' in st.session_state and st.session_state['search_results']:
        df_results = pd.DataFrame(st.session_state['search_results'])
        
        # Display the current count
        total_count = st.session_state.get('total_count', 0)
        current_displayed = len(st.session_state['search_results'])
        st.success(f"총 {total_count}개의 논문이 검색되었습니다. (현재 {current_displayed}개 표시)")
        
        # Pagination / Load More
        total_count = st.session_state.get('total_count', 0)
        current_retstart = st.session_state.get('retstart', 0)
        
        if current_retstart < total_count:
            if st.button("🔽 더 보기 (Load More)"):
                with st.spinner("다음 논문 데이터를 가져오고 번역하는 중입니다. 잠시만 기다려주세요... ⏳"):
                    try:
                        more_results, _ = fetch_pubmed_papers(
                            st.session_state['keyword'], st.session_state['start_year'], st.session_state['start_month'], 
                            st.session_state['end_year'], st.session_state['end_month'], st.session_state['free_full_text'], 
                            st.session_state['pub_type'], st.session_state['max_results'], retstart=current_retstart
                        )
                        if more_results:
                            st.session_state['search_results'].extend(more_results)
                            st.session_state['retstart'] += st.session_state['max_results']
                            st.session_state.select_all = False
                            st.session_state.editor_key = st.session_state.get('editor_key', 0) + 1
                            st.rerun()
                    except Exception as e:
                        st.error(f"결과를 더 가져오는 중 오류가 발생했습니다: {e}")
                
        if 'save_success' in st.session_state:
            st.success(st.session_state['save_success'])
            del st.session_state['save_success']
            
        st.subheader("검색 결과")
        
        # Add a Master Checkbox for Select All
        if 'select_all' not in st.session_state:
            st.session_state.select_all = False
            
        def toggle_select_all():
            st.session_state.select_all = not st.session_state.select_all
            st.session_state.editor_key = st.session_state.get('editor_key', 0) + 1
            
        st.checkbox("현재 화면의 (새로운) 논문 전체 선택", value=st.session_state.select_all, on_change=toggle_select_all, key="master_checkbox")
        
        # Identify already saved PMIDs
        df_db = get_papers()
        saved_pmids = set(df_db['pmid']) if not df_db.empty else set()
        
        # Ensure we recreate dataframe based on updated session state
        df_results = pd.DataFrame(st.session_state['search_results'])
        
        # Add Status Column
        if "상태" not in df_results.columns:
            df_results.insert(0, "상태", df_results["pmid"].apply(lambda p: "✅ 저장됨" if p in saved_pmids else "🆕 새 논문"))
        else:
            df_results["상태"] = df_results["pmid"].apply(lambda p: "✅ 저장됨" if p in saved_pmids else "🆕 새 논문")
            
        # Add a selection column for checkboxes
        if "선택" not in df_results.columns:
            df_results.insert(0, "선택", st.session_state.select_all)
        else:
            df_results["선택"] = st.session_state.select_all
            
        # Force already saved ones to be unselected
        df_results.loc[df_results["상태"] == "✅ 저장됨", "선택"] = False
        
        if 'editor_key' not in st.session_state:
            st.session_state.editor_key = 0
            
        # Data editor allowing users to check rows
        edited_df = st.data_editor(
            df_results,
            hide_index=True,
            column_config={
                "선택": st.column_config.CheckboxColumn(
                    "선택", 
                    help="DB에 저장할 논문을 체크하세요", 
                    default=False
                ),
                "상태": st.column_config.TextColumn(
                    "상태",
                    help="DB 저장 여부"
                ),
                "url": st.column_config.LinkColumn("링크")
            },
            disabled=["상태", "pmid", "title", "authors", "journal", "year", "abstract", "url", "pub_types", "keywords"],
            use_container_width=True,
            key=f"data_editor_{st.session_state.editor_key}"
        )
        
        if st.button("DB에 저장하기 (선택된 항목)", type="secondary"):
            selected_rows = edited_df[edited_df["선택"]]
            # Ignore already saved ones if user manually checked them
            valid_rows = selected_rows[selected_rows["상태"] == "🆕 새 논문"]
            
            if valid_rows.empty:
                st.warning("새로 저장할 데이터가 선택되지 않았습니다. (이미 저장된 항목은 무시됩니다)")
            else:
                saved_count = 0
                for _, row in valid_rows.iterrows():
                    # Compose dict
                    paper_dict = {
                        "pmid": str(row["pmid"]),
                        "title": row["title"],
                        "authors": row["authors"],
                        "journal": row["journal"],
                        "year": str(row["year"]),
                        "abstract": row["abstract"],
                        "url": row["url"],
                        "pub_types": row.get("pub_types", ""),
                        "keywords": row.get("keywords", ""),
                        "original_title": row.get("original_title", row["title"]),
                        "original_abstract": row.get("original_abstract", row["abstract"]),
                    }
                    
                    # Run rule-based classifier
                    classifications = dummy_classify_abstract(row["abstract"])
                    paper_dict.update(classifications)
                    
                    # Upsert to db
                    upsert_paper(paper_dict)
                    saved_count += 1
                    
                st.session_state.select_all = False
                st.session_state.editor_key = st.session_state.get('editor_key', 0) + 1
                st.session_state['save_success'] = f"성공적으로 {saved_count}개의 논문을 DB에 저장했습니다! [내 지식 서재] 탭에서 확인하세요."
                st.rerun()

# ----------------- #
# Tab 2: Library    #
# ----------------- #
with tab2:
    st.header("내 지식 서재")
    
    # Fetch all papers from DB
    df_db = get_papers()
    
    if df_db.empty:
        st.info("아직 DB에 저장된 논문이 없습니다. [논문 수집 및 저장] 탭에서 논문을 검색하고 저장해 보세요.")
    else:
        st.subheader("데이터 검색 및 필터링")
        
        # Keyword search for Tab 2
        library_keyword = st.text_input("내 서재 내 키워드 검색 (제목 또는 요약문 포함)", value="")
        
        col_f1, col_f2, col_f3 = st.columns(3)
        
        # Distinct values for dropdowns
        disease_areas = ["All"] + sorted(df_db["disease_area"].dropna().unique().tolist())
        evidence_levels = ["All"] + sorted(df_db["evidence_level"].dropna().unique().tolist())
        years = ["All"] + sorted(df_db["year"].astype(str).dropna().unique().tolist(), reverse=True)
        
        with col_f1:
            selected_disease = st.selectbox("Disease Area (질환 영역)", disease_areas)
        with col_f2:
            selected_evidence = st.selectbox("Evidence Level (증거 수준)", evidence_levels)
        with col_f3:
            selected_year = st.selectbox("출판 연도 (Year)", years)
            
        filters = {
            "keyword": library_keyword.strip() if library_keyword.strip() else None,
            "disease_area": selected_disease,
            "evidence_level": selected_evidence,
            "year": selected_year
        }
        
        # Get filtered papers
        filtered_df = get_papers(filters)
        
        st.write(f"**총 {len(filtered_df)}개의 논문**이 표시됩니다.")
        
        if 'delete_success' in st.session_state:
            st.success(st.session_state['delete_success'])
            del st.session_state['delete_success']
            
        # Add a Master Checkbox for Select All in Library
        if 'lib_select_all' not in st.session_state:
            st.session_state.lib_select_all = False
            
        def toggle_lib_select_all():
            st.session_state.lib_select_all = not st.session_state.lib_select_all
            st.session_state.lib_editor_key = st.session_state.get('lib_editor_key', 0) + 1
            
        st.checkbox("현재 화면의 논문 전체 선택", value=st.session_state.lib_select_all, on_change=toggle_lib_select_all, key="master_lib_checkbox")
            
        # Add checkbox column for deletion
        if "선택" not in filtered_df.columns:
            filtered_df.insert(0, "선택", st.session_state.lib_select_all)
        else:
            filtered_df["선택"] = st.session_state.lib_select_all
            
        if 'lib_editor_key' not in st.session_state:
            st.session_state.lib_editor_key = 0
            
        with st.form("delete_form"):
            edited_lib_df = st.data_editor(
                filtered_df,
                hide_index=True,
                column_config={
                    "선택": st.column_config.CheckboxColumn("선택", help="삭제할 논문을 체크하세요", default=False),
                    "url": st.column_config.LinkColumn("링크")
                },
                disabled=["pmid", "title", "authors", "journal", "year", "abstract", "url", 
                          "domain", "disease_area", "scfa_role", "evidence_level", 
                          "claim_summary", "mechanism_tags", "population", "intervention", "outcomes",
                          "original_title", "original_abstract", "pub_types", "keywords"],
                use_container_width=True,
                key=f"lib_data_editor_{st.session_state.lib_editor_key}"
            )
            
            delete_submitted = st.form_submit_button("🗑️ 선택한 논문 삭제하기", type="primary")
            if delete_submitted:
                to_delete = edited_lib_df[edited_lib_df["선택"]]
                if to_delete.empty:
                    st.warning("삭제할 논문을 하나 이상 선택해 주세요.")
                else:
                    pmids_to_delete = to_delete["pmid"].astype(str).tolist()
                    delete_papers(pmids_to_delete)
                    
                    st.session_state.lib_editor_key = st.session_state.get('lib_editor_key', 0) + 1
                    st.session_state.lib_select_all = False
                    
                    # Also force reset of Tab 1 states
                    st.session_state.select_all = False
                    st.session_state.editor_key = st.session_state.get('editor_key', 0) + 1
                    
                    st.session_state['delete_success'] = f"성공적으로 {len(pmids_to_delete)}개의 논문을 삭제했습니다."
                    st.rerun()
        
        st.subheader("데이터 추출 (Export)")
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            # Excel Download Button
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Knowledge Base')
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 Excel 결과 다운로드 (.xlsx)",
                data=excel_data,
                file_name=f"pubmed_knowledge_base_{datetime.datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        with col_btn2:
            # Markdown Generation Toggle
            if st.button("📝 Markdown 브리프 생성"):
                st.session_state['generate_md'] = True
                
        if st.session_state.get('generate_md', False):
            st.markdown("---")
            st.markdown("### 📄 마크다운 브리프 (Markdown Brief)")
            
            if filtered_df.empty:
                st.warning("추출할 데이터가 없습니다.")
            else:
                md_content = ""
                for _, row in filtered_df.iterrows():
                    # Format: 제목(연도, 저널) / claim_summary / evidence_level / mechanism_tags / url 형태의 불릿 포인트.
                    title = row.get("title", "")
                    year = row.get("year", "")
                    journal = row.get("journal", "")
                    claim = row.get("claim_summary", "")
                    evidence = row.get("evidence_level", "")
                    mechanism = row.get("mechanism_tags", "")
                    url = row.get("url", "")
                    
                    md_item = f"**{title}** ({year}, *{journal}*)\n"
                    md_item += f"- **Claim Summary**: {claim}\n"
                    md_item += f"- **Evidence Level**: {evidence}\n"
                    md_item += f"- **Mechanism Tags**: {mechanism}\n"
                    md_item += f"- **URL**: [Link]({url})\n\n"
                    
                    md_content += md_item
                    
                st.text_area("결과 복사하기 (Ctrl+C / Cmd+C)", value=md_content, height=300)
                
                st.download_button(
                    label="Markdown 파일로 바로 저장 (.md)",
                    data=md_content,
                    file_name=f"pubmed_brief_{datetime.datetime.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown"
                )
