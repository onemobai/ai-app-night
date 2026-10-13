# --- 第 1 部分：导入工具库 ---
import os                               # Python自带，用来读取系统环境变量
import streamlit as st                  # 画网页用的，起个外号叫 st
from openai import OpenAI               # 跟大模型通信的“通信员”
import db                               # 我们自己写的档案管理员，负责存/取聊天记录

# --- 第 2 部分：网页基本设置 ---
st.set_page_config(page_title="AI 聊天助手", page_icon="🤖")  # 设置浏览器标签页标题
st.title("🤖 我的第一个 AI 应用")                             # 网页最上面的大标题

# --- 第 3 部分：侧边栏配置区 ---
with st.sidebar:                        # 下面的代码都会显示在左侧侧边栏里
    st.header("配置")
    
    # API Key 输入框（type="password" 会隐藏输入，防止密码泄露）
    api_key = st.text_input("API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    
    # 请求地址输入框
    base_url = st.text_input(
        "Base URL",
        value=os.getenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    )
    
    # 模型名输入框
    model = st.text_input(
        "模型名",
        value=os.getenv("OPENAI_MODEL", "glm-4-flash")
    )
    
    # 系统提示词，用来告诉AI它要扮演什么角色
    system_prompt = st.text_area(
        "System Prompt",
        value="你是一个简洁、友好的AI助手。回答先给结论，再给步骤。"
    )
    
    # 温度滑块，控制回答的随机性（0最严谨，1最发散）
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)

    # [新增] 文件上传按钮，只允许上传 txt 格式
    uploaded_file = st.file_uploader("上传一个TXT文件", type=["txt"])

    # 清空对话按钮
    if st.button("清空对话"):
        db.clear_messages()  # 去数据库删掉所有聊天记录
        st.session_state.messages = [{"role": "system", "content": system_prompt}]  # 清空内存里的记录
        st.rerun()           # 刷新页面

# --- 第 4 部分：初始化聊天记录 ---
# 如果内存里还没有历史记录（比如刚打开页面）
if "messages" not in st.session_state:
    history = db.load_messages()  # 先从数据库里翻一翻
    
    # 如果数据库里是空的（新用户）
    if not history:
        history = [{"role": "system", "content": system_prompt}]  # 放个初始提示词
        
    st.session_state.messages = history  # 把记录存进内存

# 同步最新的系统提示词到内存里
if st.session_state.messages and st.session_state.messages[0]["role"] == "system":
    st.session_state.messages[0]["content"] = system_prompt

# --- 第 5 部分：把历史记录画在网页上 ---
for msg in st.session_state.messages:
    if msg["role"] != "system":             # 系统提示词不显示出来
        with st.chat_message(msg["role"]):  # 画聊天气泡
            st.markdown(msg["content"])

# --- 第 6 部分：读取上传的文件内容 [新增] ---
file_content = ""                           # 准备一个空字符串
if uploaded_file is not None:               # 如果用户确实传了文件
    file_content = uploaded_file.read().decode("utf-8")  # 把文件读成文字
    st.sidebar.success("文件读取成功！")      # 左侧给个提示

# --- 第 7 部分：聊天主逻辑 ---
prompt = st.chat_input("请指示")  # 底部输入框

if prompt:  # 如果用户发了消息
    if not api_key:  # 没填 API Key 就提示并停止
        st.error("请先在左侧填写 API Key")
        st.stop()

    # 1. 把用户的提问存进内存和数据库
    st.session_state.messages.append({"role": "user", "content": prompt})
    db.save_message("user", prompt)
    
    # 2. 网页上画出用户说的话
    with st.chat_message("user"):
        st.markdown(prompt)

    # 3. 建立与大模型的连接
    client = OpenAI(api_key=api_key, base_url=base_url)

    with st.chat_message("assistant"):
        placeholder = st.empty()  # 占个坑，用来显示回答
        full_text = ""            # 接收AI回答的字符串

        try:
            # 准备发送给AI的消息列表（复制一份，不影响原本的内存记录）
            messages_to_send = st.session_state.messages.copy()
            
            # [新增] 如果用户上传了文件，就把文件内容作为背景知识插进去
            if file_content:
                messages_to_send.insert(1, {
                    "role": "system", 
                    "content": f"以下是用户上传的文件内容，请严格根据这些内容来回答问题：\n\n{file_content}"
                })

            # 发送请求，stream=True 开启流式输出
            stream = client.chat.completions.create(
                model=model,
                messages=messages_to_send,  # 注意这里改成了 messages_to_send
                stream=True,
                temperature=temperature,
            )

            # 不断接收 AI 传回来的文字
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                full_text += delta
                placeholder.markdown(full_text + "▌")  # 模拟打字机光标

            placeholder.markdown(full_text)  # 去掉光标，显示完整回答
            
            # 4. 把 AI 的回答也存进内存和数据库
            st.session_state.messages.append(
                {"role": "assistant", "content": full_text}
            )
            db.save_message("assistant", full_text)

        except Exception as e:  # 如果报错
            st.error(f"调用失败：{e}")
            st.info("检查 API Key、Base URL、模型名，或网络。")