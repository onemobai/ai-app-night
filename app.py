import os
import streamlit as st
from openai import OpenAI
import db

# --- 1. 网页基本设置 ---
st.set_page_config(page_title="AI 聊天助手", page_icon="🤖")
st.title("🤖 我的第一个 AI 应用")

# --- 2. 初始化数据库（防云端报错）---
db.init_db()

# --- 3. 侧边栏配置区 ---
with st.sidebar:
    st.header("配置")
    
    # 【安全逻辑】优先从环境变量读 Key，读到了就不在界面显示，防止泄露
    api_key_env = os.getenv("OPENAI_API_KEY", "")
    if api_key_env:
        api_key = api_key_env
    else:
        api_key = st.text_input("API Key", type="password", value="")
    
    base_url = st.text_input(
        "Base URL",
        value=os.getenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    )
    model = st.text_input(
        "模型名",
        value=os.getenv("OPENAI_MODEL", "glm-4-flash")
    )
    
    # 【核心】定义系统提示词
    system_prompt = st.text_area(
        "System Prompt",
        value="你是一个简洁、友好的AI助手。回答先给结论，再给步骤。"
    )
    
    # 温度调节
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)

    # 文件上传
    uploaded_file = st.file_uploader("上传一个TXT文件", type=["txt"])

    # 清空对话
    if st.button("清空对话"):
        db.clear_messages()
        st.session_state.messages = [{"role": "system", "content": system_prompt}]
        st.rerun()

# --- 4. 初始化聊天记录 ---
if "messages" not in st.session_state:
    history = db.load_messages()
    if not history:
        history = [{"role": "system", "content": system_prompt}]
    st.session_state.messages = history

# 同步最新的人设
if st.session_state.messages and st.session_state.messages[0]["role"] == "system":
    st.session_state.messages[0]["content"] = system_prompt

# --- 5. 把历史记录画在网页上 ---
for msg in st.session_state.messages:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# --- 6. 读取上传的文件 ---
file_content = ""
if uploaded_file is not None:
    file_content = uploaded_file.read().decode("utf-8")
    st.sidebar.success("文件读取成功！")

# --- 7. 聊天主逻辑 ---
prompt = st.chat_input("输入你的问题，例如：用三句话解释什么是RAG")

if prompt:
    if not api_key:
        st.error("请先在左侧填写 API Key")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    db.save_message("user", prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)

    client = OpenAI(api_key=api_key, base_url=base_url)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_text = ""

        try:
            messages_to_send = st.session_state.messages.copy()
            if file_content:
                messages_to_send.insert(1, {
                    "role": "system", 
                    "content": f"以下是用户上传的文件内容，请严格根据这些内容来回答问题：\n\n{file_content}"
                })

            stream = client.chat.completions.create(
                model=model,
                messages=messages_to_send,
                stream=True,
                temperature=temperature,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                full_text += delta
                placeholder.markdown(full_text + "▌")

            placeholder.markdown(full_text)
            st.session_state.messages.append(
                {"role": "assistant", "content": full_text}
            )
            db.save_message("assistant", full_text)

        except Exception as e:
            st.error(f"调用失败：{e}")
            st.info("检查 API Key、Base URL、模型名，或网络。")
