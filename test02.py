import streamlit as st
import requests
import xml.etree.ElementTree as ET

def get_law_list(law_type):
    url = f"https://elaws.e-gov.go.jp/api/1/lawlists/{law_type}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        laws = []
        for law in root.findall(".//LawNameListInfo"):
            law_id = law.find("LawId").text
            law_name = law.find("LawName").text
            law_no = law.find("LawNo").text
            laws.append((law_id, law_name, law_no))
        return laws
    except requests.RequestException as e:
        st.error(f"法令リストの取得に失敗しました: {str(e)}")
        return []

def get_law_content(law_id):
    url = f"https://elaws.e-gov.go.jp/api/1/lawdata/{law_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        
        # デバッグ情報を追加
        st.write("APIレスポンス構造:")
        st.write(ET.tostring(root, encoding='unicode'))
        
        # LawFullTextタグが見つからない場合の代替処理
        law_full_text = root.find(".//LawFullText")
        if law_full_text is not None:
            content = law_full_text.text
        else:
            # LawFullTextがない場合、全てのテキストを結合
            content = "\n".join([elem.text for elem in root.iter() if elem.text])
        
        if not content:
            st.warning("法令内容が空です。APIレスポンスを確認してください。")
        return content
    except requests.RequestException as e:
        st.error(f"法令内容の取得に失敗しました: {str(e)}")
        return None

st.title("法令検索アプリ")

law_type = st.selectbox(
    "法令の種類を選択してください",
    ["1", "2", "3", "4"],
    format_func=lambda x: {
        "1": "全法令",
        "2": "憲法・法律",
        "3": "政令・勅令",
        "4": "府省令・規則"
    }[x]
)

if 'laws' not in st.session_state:
    st.session_state.laws = []

if st.button("法令リストを取得"):
    st.session_state.laws = get_law_list(law_type)

if st.session_state.laws:
    selected_law = st.selectbox(
        "法令を選択してください",
        st.session_state.laws,
        format_func=lambda x: f"{x[1]} ({x[2]})"
    )
    
    if st.button("法令内容を表示"):
        with st.spinner("法令内容を取得中..."):
            law_content = get_law_content(selected_law[0])
        if law_content:
            st.text_area("法令内容", law_content, height=300)

st.sidebar.markdown("""
## 使い方
1. 法令の種類を選択します。
2. 「法令リストを取得」ボタンをクリックします。
3. 表示された法令リストから特定の法令を選択します。
4. 「法令内容を表示」ボタンをクリックして法令の全文を表示します。
""")