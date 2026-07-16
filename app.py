import os

import httpx
import streamlit as st

from frontend.api_client import TravelApiClient


st.set_page_config(
    page_title="智能旅行规划助手",
    page_icon="🗺️",
    layout="wide",
)


@st.cache_resource
def get_api_client() -> TravelApiClient:
    return TravelApiClient(os.getenv("BACKEND_URL", "http://localhost:8000"))


def reset_conversation() -> None:
    st.session_state.conversation_id = None
    st.session_state.loaded_conversation_id = None
    st.session_state.messages = []
    if "conversation_selector" in st.session_state:
        st.session_state.conversation_selector = None


client = get_api_client()
st.session_state.setdefault("client_id", os.getenv("TRAVEL_CLIENT_ID", "local"))
st.session_state.setdefault("conversation_id", None)
st.session_state.setdefault("loaded_conversation_id", None)
st.session_state.setdefault("messages", [])

try:
    backend_health = client.health()
    backend_available = True
except (httpx.HTTPError, OSError):
    backend_health = {}
    backend_available = False


with st.sidebar:
    st.header("知识库", anchor=False)
    if backend_available:
        st.success("后端服务已连接", icon=":material/check_circle:")
        st.caption(
            f"{backend_health.get('database', 'database')} · "
            f"{backend_health.get('embedding_provider', 'embedding')}"
        )
    else:
        st.error("后端服务不可用", icon=":material/error:")

    with st.form("document_upload", border=False):
        uploaded_files = st.file_uploader(
            "导入旅游资料",
            type=["txt", "md", "pdf", "csv"],
            accept_multiple_files=True,
            max_upload_size=20,
            disabled=not backend_available,
        )
        upload_submitted = st.form_submit_button(
            "导入并索引",
            icon=":material/upload_file:",
            disabled=not backend_available or not uploaded_files,
            width="stretch",
        )

    if upload_submitted and uploaded_files:
        with st.spinner("正在解析、向量化并建立索引..."):
            try:
                imported = client.upload_documents(uploaded_files)
                ready_count = sum(item["status"] == "ready" for item in imported)
                st.success(f"已处理 {ready_count} 个文档")
            except httpx.HTTPStatusError as exc:
                detail = exc.response.json().get("detail", str(exc))
                st.error(detail)
            except httpx.HTTPError as exc:
                st.error(f"上传失败: {exc}")

    documents = []
    if backend_available:
        try:
            documents = client.list_documents()
        except httpx.HTTPError as exc:
            st.warning(f"无法读取文档列表: {exc}")

    if documents:
        ready_documents = [item for item in documents if item["status"] == "ready"]
        st.caption(
            f"{len(ready_documents)} 个可用文档 · "
            f"{sum(item['chunk_count'] for item in ready_documents)} 个分块"
        )
        document_by_id = {item["id"]: item for item in documents}
        selected_document_id = st.selectbox(
            "管理文档",
            options=list(document_by_id),
            format_func=lambda value: (
                f"{document_by_id[value]['filename']} · "
                f"{document_by_id[value]['status']} · "
                f"{document_by_id[value]['chunk_count']}块"
            ),
        )
        with st.container(horizontal=True):
            if st.button(
                "重新索引",
                icon=":material/refresh:",
                disabled=not backend_available,
            ):
                with st.spinner("正在重新索引..."):
                    try:
                        client.reindex_document(selected_document_id)
                        st.rerun()
                    except httpx.HTTPError as exc:
                        st.error(f"重新索引失败: {exc}")
            if st.button(
                "删除",
                icon=":material/delete:",
                disabled=not backend_available,
            ):
                try:
                    client.delete_document(selected_document_id)
                    st.rerun()
                except httpx.HTTPError as exc:
                    st.error(f"删除失败: {exc}")
    else:
        st.caption("知识库中暂无文档")

    st.divider()
    st.header("会话", anchor=False)
    st.button(
        "新建会话",
        icon=":material/add_comment:",
        on_click=reset_conversation,
        width="stretch",
    )

    conversations = []
    if backend_available:
        try:
            conversations = client.list_conversations(st.session_state.client_id)
        except httpx.HTTPError:
            conversations = []

    if conversations:
        conversation_by_id = {item["id"]: item for item in conversations}
        selected_conversation_id = st.selectbox(
            "历史会话",
            options=[None, *conversation_by_id],
            format_func=lambda value: (
                "当前新会话" if value is None else conversation_by_id[value]["title"]
            ),
            key="conversation_selector",
        )
        if (
            selected_conversation_id
            and selected_conversation_id != st.session_state.loaded_conversation_id
        ):
            try:
                detail = client.get_conversation(
                    selected_conversation_id,
                    st.session_state.client_id,
                )
                st.session_state.conversation_id = selected_conversation_id
                st.session_state.loaded_conversation_id = selected_conversation_id
                st.session_state.messages = detail["messages"]
                st.rerun()
            except httpx.HTTPError as exc:
                st.error(f"加载会话失败: {exc}")


st.title("智能旅行规划助手")
st.caption("实时工具、持久化知识库与来源引用")

if not st.session_state.messages and backend_available:
    suggestions = {
        "成都三日游": "从上海出发去成都玩3天，预算4000元，喜欢美食和人文景点",
        "北京亲子游": "规划北京4天亲子游，有老人和孩子同行",
        "上海攻略": "上海有哪些适合第一次去的景点和本地美食？",
    }
    selected_suggestion = st.pills(
        "示例问题",
        options=list(suggestions),
        label_visibility="collapsed",
    )
    if selected_suggestion:
        st.session_state.pending_prompt = suggestions[selected_suggestion]
        st.rerun()


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        citations = message.get("citations", [])
        if citations:
            with st.expander("查看引用资料"):
                for citation in citations:
                    page = f" · 第{citation['page']}页" if citation.get("page") else ""
                    st.markdown(
                        f"**[来源{citation['index']}] {citation['source']}{page}**  "
                        f"\n{citation['excerpt']}"
                    )
        tools = message.get("tools", [])
        if tools:
            with st.expander("查看实时工具状态"):
                for tool in tools:
                    icon = ":material/check_circle:" if tool["success"] else ":material/error:"
                    st.markdown(
                        f"{icon} `{tool['name']}` · {tool['latency_ms']}ms"
                    )


submitted_query = st.chat_input(
    "描述出发地、目的地、日期、预算和偏好",
    disabled=not backend_available,
    submit_mode="disable",
    max_chars=4000,
)
query = st.session_state.pop("pending_prompt", None) or submitted_query

if query:
    user_message = {"role": "user", "content": query}
    st.session_state.messages.append(user_message)
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.status("正在检索资料和实时信息...", expanded=False) as status:
            try:
                response = client.chat(
                    query=query,
                    client_id=st.session_state.client_id,
                    conversation_id=st.session_state.conversation_id,
                )
                st.session_state.conversation_id = response["conversation_id"]
                st.session_state.loaded_conversation_id = response["conversation_id"]
                assistant_message = {
                    "role": "assistant",
                    "content": response["answer"],
                    "citations": response.get("citations", []),
                    "tools": response.get("tools", []),
                }
                st.session_state.messages.append(assistant_message)
                status.update(label="规划完成", state="complete")
                st.markdown(response["answer"])
            except httpx.HTTPStatusError as exc:
                detail = exc.response.json().get("detail", str(exc))
                status.update(label="规划失败", state="error")
                st.error(detail)
            except httpx.HTTPError as exc:
                status.update(label="后端连接失败", state="error")
                st.error(str(exc))
