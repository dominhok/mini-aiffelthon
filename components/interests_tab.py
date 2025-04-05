import streamlit as st

def interests_tab():
    st.title("🔍 관심분야 보고서")

    # --- 관심 분야 브리핑 --- START
    interests = st.session_state.get("user_interests", "")
    briefing_result = st.session_state.get("briefing_result")
    last_briefed = st.session_state.get("last_briefed_interests")

    # 관심 분야가 있고, (결과가 없거나 or 마지막 브리핑된 관심사와 현재 관심사가 다를 때) 검색 수행 -> 조건 수정: 관심 분야가 있으면 항상 검색 수행
    if interests: # <<< 수정된 조건: 관심 분야가 존재하면 항상 브리핑 생성 시도
        # 브리핑 실행 로직은 컨테이너 밖에 위치 (스피너 표시 때문)
        if briefing_result is None: # 아직 브리핑 결과가 없으면 검색 시도
            if not st.session_state.session_initialized or not st.session_state.mcp_client:
                st.warning("시스템이 아직 준비되지 않아 관심 분야 브리핑을 생성할 수 없습니다.")
            else:
                search_tool = None
                try:
                    client = st.session_state.mcp_client
                    tools = client.get_tools()
                    search_tool = next((t for t in tools if t.name in ['pplx_search', 'perplexity_search']), None)
                except Exception as e:
                    st.error(f"브리핑을 위한 검색 도구를 찾는 중 오류 발생: {e}")

                if not search_tool:
                    st.error("Perplexity 검색 도구를 찾을 수 없습니다. MCP 설정을 확인해주세요.")
                else:
                    with st.spinner(f"'{interests}' 관련 보고서 작성중..."):
                        try:
                            loop = st.session_state.event_loop
                            search_prompt = f"Summarize the latest developments and key information about: {interests}. Provide a concise overview suitable for a briefing."
                            print(f"DEBUG: Running briefing search for: {interests}")
                            result = loop.run_until_complete(search_tool.ainvoke({"query": search_prompt}))
                            st.session_state.briefing_result = result
                            briefing_result = result
                            print(f"DEBUG: Briefing search complete for: {interests}")
                        except Exception as e:
                            st.error(f"관심 분야 브리핑 생성 중 오류 발생: {e}")
                            st.session_state.briefing_result = f"오류로 인해 브리핑 생성에 실패했습니다: {e}"
                            briefing_result = st.session_state.briefing_result

    # 브리핑 결과 표시 컨테이너 또는 안내 메시지
    if interests and briefing_result:
        with st.container(border=True):
            st.subheader(f"✨ '{interests}' 관심 분야 브리핑")
            st.markdown(briefing_result)
        st.divider() # 브리핑과 직접 검색 사이 구분선
    elif not interests: # 관심 분야가 없을 때 안내 메시지 표시
        st.info("💡 사이드바의 '관심 분야 설정'에서 관심사를 등록하고 맞춤 보고서를 받아보세요!")
        st.divider() # 안내 메시지와 직접 검색 사이 구분선
    # --- 관심 분야 브리핑 --- END

    # --- 사용자 직접 검색 --- START
    with st.container(border=True):
        st.subheader("직접 검색하기") # 섹션 제목 추가
        search_query = st.text_input("검색어 입력", key="search_query_input", label_visibility="collapsed") # 라벨 숨김

        if st.button("검색 실행", key="search_button"):
            if not search_query:
                st.warning("검색어를 입력해주세요.")
            elif not st.session_state.session_initialized or not st.session_state.mcp_client:
                st.error("시스템이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.")
            else:
                search_tool = None
                try:
                    client = st.session_state.mcp_client
                    tools = client.get_tools()
                    search_tool = next((t for t in tools if t.name == 'perplexity_search'), None)
                except Exception as e:
                    st.error(f"검색 도구를 찾는 중 오류 발생: {e}")

                if not search_tool:
                    st.error("Perplexity 검색 도구를 찾을 수 없습니다. MCP 설정을 확인해주세요.")
                else:
                    with st.spinner("Perplexity AI에 문의 중..."):
                        try:
                            loop = st.session_state.event_loop
                            search_result = loop.run_until_complete(search_tool.ainvoke({"query": search_query}))
                            
                            # 검색 결과 표시 (컨테이너 내부)
                            st.markdown("--- *검색 결과* ---") # 결과 구분선 추가
                            st.markdown(search_result)
                        except Exception as e:
                            st.error(f"검색 실행 중 오류 발생: {e}")
    # --- 사용자 직접 검색 --- END
