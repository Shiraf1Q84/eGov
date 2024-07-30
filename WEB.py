import os
import streamlit as st
import google.generativeai as genai
from PyPDF2 import PdfReader
import markdown
import requests
import xml.etree.ElementTree as ET

# Streamlitページ設定
st.set_page_config(
    page_title="Gemini PDFベースチャットボット with 法令検索",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# セッション状態の初期化
if "documents" not in st.session_state:
    st.session_state.documents = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "laws" not in st.session_state:
    st.session_state.laws = []
if "selected_law_content" not in st.session_state:
    st.session_state.selected_law_content = None
if "selected_law_name" not in st.session_state:
    st.session_state.selected_law_name = None

# 法令検索関連の関数
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
        
        # 法令の全文を取得
        law_contents = []
        for elem in root.iter():
            if elem.text and elem.text.strip():
                law_contents.append(elem.text.strip())
        
        content = "\n".join(law_contents)
        
        if not content:
            st.warning("法令内容が空です。APIレスポンスを確認してください。")
            return None
        return content
    except requests.RequestException as e:
        st.error(f"法令内容の取得に失敗しました: {str(e)}")
        return None

# ファイル処理関数
def extract_text_from_pdf(file):
    pdf_reader = PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_markdown(file):
    content = file.read().decode("utf-8")
    html = markdown.markdown(content)
    return html

# プロンプト生成関数
def generate_prompt(system_prompt, context, user_input):
    prompt = f"{system_prompt}\n\n"
    prompt += "参考文書:\n"
    prompt += f"{context}\n\n"
    prompt += f"ユーザーの質問: {user_input}\n\n"
    if st.session_state.selected_law_content and st.session_state.selected_law_name:
        prompt += f"関連法令: {st.session_state.selected_law_name}\n"
        prompt += f"法令内容:\n{st.session_state.selected_law_content}\n\n"

    prompt += """
    上記の情報を基に、ユーザーの質問に答えてください。関連法令からの情報を使用する場合は、必ず該当する法令名と条文番号を明記してください。
    法令の解釈が必要な場合は、その旨を明確に述べ、可能な解釈を示してください。
    情報が不足している場合は、どのような追加情報が必要かを説明してください。
    """
    return prompt

# メイン関数
def main():
    st.title("PDFベースチャットボット with 法令検索 (Gemini)")

    # サイドバーの設定
    with st.sidebar:
        st.subheader("設定")
        api_key = st.text_input("Google API キーを入力してください:", type="password")
        if st.button("APIキーを設定"):
            genai.configure(api_key=api_key)
            st.success("APIキーが設定されました")

        model_name = st.selectbox("モデルを選択してください:", ["gemini-1.5-pro", "gemini-pro"])

        st.subheader("ファイルアップロード")
        uploaded_files = st.file_uploader(
            "PDFまたはマークダウンファイルを選択してください",
            accept_multiple_files=True,
            type=["pdf", "md"],
        )

        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_extension = os.path.splitext(uploaded_file.name)[1]
                if file_extension == ".pdf":
                    text = extract_text_from_pdf(uploaded_file)
                elif file_extension == ".md":
                    text = extract_text_from_markdown(uploaded_file)
                else:
                    st.warning(f"未対応のファイル形式です: {uploaded_file.name}")
                    continue
                st.session_state.documents.append({"name": uploaded_file.name, "content": text})
            st.success(f"{len(uploaded_files)}個のファイルがアップロードされました。")

        st.subheader("法令検索")
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

        if st.button("法令リストを取得"):
            st.session_state.laws = get_law_list(law_type)

        if st.session_state.laws:
            selected_law = st.selectbox(
                "法令を選択してください",
                st.session_state.laws,
                format_func=lambda x: f"{x[1]} ({x[2]})"
            )
            
            if st.button("法令内容を取得"):
                with st.spinner("法令内容を取得中..."):
                    law_content = get_law_content(selected_law[0])
                    if law_content:
                        st.session_state.selected_law_content = law_content
                        st.session_state.selected_law_name = selected_law[1]
                        st.success("法令内容を取得しました。全文を確認できます。")
                    else:
                        st.error("法令内容の取得に失敗しました。")

    # メインエリア
    tabs = st.tabs(["チャット", "法令全文"])

    with tabs[0]:  # チャットタブ
        system_prompt = st.text_area(
            "システムプロンプトを入力してください",
            """
            あなたはナレッジベースに提供されている書類と最新の法令検索結果に基づいて情報を提供するチャットボットです。
            利用者の質問に、正確かつなるべく詳細に、参考資料を引用しながら答えてください。
            情報は800文字以上、4000文字以内に収めてください。
            マークダウン形式で見やすく出力してください。
            情報源を明記して回答するように努めてください。
            複数の解釈がある場合は、それぞれを提示してください。
            与えられた情報だけでは判断できない場合には、判断できない旨を伝えてください。
            法令の解釈が必要な場合は、その旨を明確に述べ、可能な解釈を示してください。
            検索結果が提供された場合、それらを参照しながら回答してください。
            """,
            height=300
        )

        # チャット履歴の表示
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # ユーザー入力
        user_input = st.chat_input("質問を入力してください")

        if user_input and api_key:
            # ユーザーの質問をチャット履歴に追加
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            # Geminiモデルの初期化
            model = genai.GenerativeModel(model_name)

            # コンテキストの作成
            context = ""
            for doc in st.session_state.documents:
                context += f"ファイル名: {doc['name']}\n"
                context += f"内容:\n{doc['content']}\n\n"

            # プロンプトの生成
            prompt = generate_prompt(system_prompt, context, user_input)

            # プロンプトを表示
            st.subheader("生成されたプロンプト")
            st.text_area("", prompt, height=300)

            # ストリーミングレスポンスを生成
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                response = model.generate_content(prompt, stream=True)
                full_response = ""
                for chunk in response:
                    full_response += chunk.text
                    response_placeholder.markdown(full_response + "▌")
                response_placeholder.markdown(full_response)

            # アシスタントの回答をチャット履歴に追加
            st.session_state.chat_history.append({"role": "assistant", "content": full_response})

        elif not api_key:
            st.warning("APIキーを設定してください。")

    with tabs[1]:  # 法令全文タブ
        if st.session_state.selected_law_content and st.session_state.selected_law_name:
            st.subheader(f"法令全文: {st.session_state.selected_law_name}")
            st.text_area("", st.session_state.selected_law_content, height=600)
        else:
            st.info("法令が選択されていません。サイドバーから法令を選択し、内容を取得してください。")

if __name__ == "__main__":
    main()