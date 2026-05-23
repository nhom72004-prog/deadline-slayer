from datetime import datetime
import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from zoneinfo import ZoneInfo
import json
import os
import random
import streamlit as st

# --- TẠO CHÌA KHÓA TRÊN CLOUD TỪ SECRETS ---
if not os.path.exists("credentials.json"):
    if "gcp_service_account" in st.secrets:
        with open("credentials.json", "w") as f:
            json.dump(dict(st.secrets["gcp_service_account"]), f)

# ─── TIMEZONE CONFIG ────────────────────────────────────────
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
def NOW():
    return datetime.now(TZ)

# ─── PAGE CONFIGURATION ──────────────────────────────────────
st.set_page_config(
    page_title="Deadline Slayer ⚔️",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "sheet_name" not in st.session_state:
    st.session_state["sheet_name"] = "DeadlineSlayer_DB"
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = None

# ─── CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
[data-testid="metric-container"] {
    background: #16161a; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px; padding: 16px !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.2);
}
.stButton > button[kind="primary"] {
    background: #5865F2; border: none; border-radius: 8px;
    font-weight: 700; color: white;
}
.stButton > button[kind="primary"]:hover { background: #404EED; }

/* ── CHAT BUBBLES ── */
.chat-wrap { display: flex; flex-direction: column; gap: 8px; padding: 6px 2px; }
.msg-bubble { display: flex; align-items: flex-end; gap: 8px; max-width: 85%; }
.msg-avatar {
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; flex-shrink: 0; letter-spacing: 0.5px;
}
.msg-body { display: flex; flex-direction: column; gap: 2px; }
.msg-meta { font-size: 11px; padding: 0 6px; }
.msg-text {
    padding: 9px 14px; border-radius: 16px;
    font-size: 14px; line-height: 1.55; word-break: break-word;
    border: 1px solid transparent;
}

/* Tin người khác — nhóm */
.msg-other { align-self: flex-start; }
.msg-other .msg-meta { color: #666; }
.msg-other .msg-text {
    background: #f0f1f3; color: #1a1a1a;
    border-color: #e0e2e5; border-radius: 4px 16px 16px 16px;
}
.msg-other .msg-avatar { background: #dde2ff; color: #3d47cc; }

/* Tin của tôi */
.msg-me { align-self: flex-end; flex-direction: row-reverse; }
.msg-me .msg-meta { color: #888; text-align: right; }
.msg-me .msg-text {
    background: #5865F2; color: #ffffff;
    border-color: #4752c4; border-radius: 16px 4px 16px 16px;
}
.msg-me .msg-avatar { background: #5865F2; color: #ffffff; }

/* Tin DM người khác */
.msg-dm { align-self: flex-start; }
.msg-dm .msg-meta { color: #666; }
.msg-dm .msg-text {
    background: #f0f4ff; color: #1a1a1a;
    border-color: #c5d0ff; border-radius: 4px 16px 16px 16px;
}
.msg-dm .msg-avatar { background: #c5d0ff; color: #2e3ab4; }

/* DARK MODE */
@media (prefers-color-scheme: dark) {
    .msg-other .msg-text { background: #2b2d31; color: #e8e9eb; border-color: #3f4147; }
    .msg-other .msg-avatar { background: #3d4270; color: #9ba4f5; }
    .msg-other .msg-meta { color: #888; }
    .msg-dm .msg-text { background: #1e2340; color: #e2e6ff; border-color: #3b4680; }
    .msg-dm .msg-avatar { background: #2a3370; color: #9ba8ff; }
    .msg-dm .msg-meta { color: #888; }
    .msg-me .msg-meta { color: #aaa; }
}

/* Separator ngày */
.date-sep {
    text-align: center; font-size: 11px; color: #aaa;
    margin: 6px 0; display: flex; align-items: center; gap: 8px;
}
.date-sep::before, .date-sep::after {
    content: ''; flex: 1; height: 1px; background: currentColor; opacity: 0.3;
}

/* Empty state */
.chat-empty { text-align: center; padding: 36px 20px; color: #999; font-size: 14px; }
.chat-empty-icon { font-size: 34px; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  1. GOOGLE SHEETS SCHEMA
# ═══════════════════════════════════════════════════════════

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

WS_TASKS  = "Tasks"
WS_USERS  = "Users"
WS_GROUPS = "Groups"
WS_PROOFS = "Proofs"
WS_CHAT   = "ChatRoom"
WS_DM     = "DirectMessages"

TASK_COLS  = ["ID", "Tên_Công_Việc", "Môn_Học", "Người_Phụ_Trách_ID", "Deadline",
              "Độ_Ưu_Tiên", "Trạng_Thái", "Tiến_Độ_%", "Giai_Đoạn_Hiện_Tại",
              "Ghi_Chú", "Nhắc_Mỗi_Phút", "Nhắc_Lần_Cuối", "Ngày_Tạo", "Ngày_Cập_Nhật"]
USER_COLS  = ["User_ID", "Password", "Tên", "Email", "Bạn_Bè", "Discord_Webhook_DM", "Ngày_Tạo"]
GROUP_COLS = ["Group_ID", "Tên_Nhóm", "Trưởng_Nhóm_ID", "Thành_Viên_IDs", "Discord_Webhook", "Ngày_Tạo"]
PROOF_COLS = ["Task_ID", "Người_Nộp_ID", "Thời_Gian", "Mô_Tả", "Giai_Đoạn", "URL_File"]
CHAT_COLS  = ["Thời_Gian", "Người_Gửi_ID", "Group_Nhận_ID", "Nội_Dung"]
DM_COLS    = ["Thời_Gian", "Người_Gửi_ID", "Người_Nhận_ID", "Nội_Dung"]

# ═══════════════════════════════════════════════════════════
#  2. LỜI NHẮN HỆ THỐNG
# ═══════════════════════════════════════════════════════════

def msg_login_success(name):
    return random.choice([
        f"⚔️ Chào chiến binh **{name}**! Deadline đang run rẩy trước sự hiện diện của bạn!",
        f"🔥 YO **{name}**! Sẵn sàng nghiền nát deadline chưa? Let's GOOO!",
    ])

def msg_login_fail():
    return "🤔 Hmm... ID hay mật khẩu có vẻ sai sai? Thử lại xem sao!"

def msg_register_success(new_id):
    return f"🎉 WELCOME TO THE SQUAD! ID của bạn là **`{new_id}`** — nhớ kỹ nhé!"

def msg_task_assigned(task_name, assignee_name):
    return f"🚀 Lệnh đã ban! **{assignee_name}** vừa nhận nhiệm vụ **{task_name}**!"

def msg_progress_saved(percent):
    return f"📝 Đã lưu tiến độ {percent}% thành công!"

def msg_friend_added(name):
    return f"🤝 **{name}** đã vào danh sách bạn bè!"

def msg_group_created(grp_name):
    return f"🏰 Nhóm **{grp_name}** đã được thành lập thành công!"

def msg_webhook_saved():
    return "🤖 Discord Webhook đã được kết nối!"

def discord_task_assigned(task_name, assignee_name, deadline, priority):
    return f"📌 **NHIỆM VỤ MỚI:** {task_name} | Người nhận: {assignee_name} | Hạn: {deadline} [{priority}]"

def discord_group_created(grp_name):
    return f"🎊 **BIỆT ĐỘI MỚI ĐÃ THÀNH LẬP:** Nhóm **{grp_name}** chính thức ra đời!"

def discord_group_chat(sender_name, group_label, content):
    return f"💬 **{sender_name}** › [{group_label}]: {content}"

def discord_dm(sender_name, content):
    return f"📩 **Tin nhắn riêng từ {sender_name}**: {content}"

# ═══════════════════════════════════════════════════════════
#  3. GOOGLE SHEETS CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════

@st.cache_resource(ttl=15)
def get_sheets_client():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None

def init_spreadsheet_structure(ss):
    existing = [ws.title for ws in ss.worksheets()]
    schemas = {
        WS_TASKS: TASK_COLS, WS_USERS: USER_COLS, WS_GROUPS: GROUP_COLS,
        WS_PROOFS: PROOF_COLS, WS_CHAT: CHAT_COLS, WS_DM: DM_COLS,
    }
    for name, cols in schemas.items():
        if name not in existing:
            ws = ss.add_worksheet(title=name, rows=1000, cols=len(cols))
            ws.append_row(cols)

@st.cache_data(ttl=1)
def fetch_all_data():
    client = get_sheets_client()
    empty_dict = {
        "tasks":  pd.DataFrame(columns=TASK_COLS), "users":  pd.DataFrame(columns=USER_COLS),
        "groups": pd.DataFrame(columns=GROUP_COLS), "proofs": pd.DataFrame(columns=PROOF_COLS),
        "chat":   pd.DataFrame(columns=CHAT_COLS),  "dm":     pd.DataFrame(columns=DM_COLS),
    }
    if not client:
        return empty_dict
    try:
        ss = client.open(st.session_state["sheet_name"])
        init_spreadsheet_structure(ss)
        def get_df(name, cols):
            all_vals = ss.worksheet(name).get_all_values()
            if not all_vals or len(all_vals) <= 1:
                return pd.DataFrame(columns=cols)
            df = pd.DataFrame(all_vals[1:], columns=all_vals[0])
            df = df.loc[:, ~df.columns.duplicated()]
            return df.reindex(columns=cols).fillna("")
        return {
            "tasks":  get_df(WS_TASKS,  TASK_COLS),  "users":  get_df(WS_USERS,  USER_COLS),
            "groups": get_df(WS_GROUPS, GROUP_COLS), "proofs": get_df(WS_PROOFS, PROOF_COLS),
            "chat":   get_df(WS_CHAT,   CHAT_COLS),   "dm":     get_df(WS_DM,     DM_COLS),
        }
    except Exception:
        return empty_dict

def get_worksheet_target(name: str):
    client = get_sheets_client()
    if not client: return None
    try:
        return client.open(st.session_state["sheet_name"]).worksheet(name)
    except Exception:
        return None

def append_row_data(name: str, row: list):
    import time
    ws = get_worksheet_target(name)
    if ws:
        ws.append_row(row, value_input_option="USER_ENTERED")
        time.sleep(0.5)
        fetch_all_data.clear()

def update_cell_by_id(ws_name, id_col_name, item_id, update_col_name, new_val, schema_cols):
    ws = get_worksheet_target(ws_name)
    if not ws: return
    try:
        id_col_idx     = schema_cols.index(id_col_name) + 1
        update_col_idx = schema_cols.index(update_col_name) + 1
        cell = ws.find(str(item_id))
        if cell and cell.col == id_col_idx:
            ws.update_cell(cell.row, update_col_idx, new_val)
            fetch_all_data.clear()
    except Exception as e:
        st.error(f"💀 Lỗi đồng bộ cell: {e}")

# ─── DISCORD & HELPERS ──────────────────────────────────────
def push_to_discord(message: str, webhook_url: str = "") -> bool:
    if not webhook_url or "discord.com/api/webhooks" not in webhook_url: return False
    try:
        resp = requests.post(webhook_url, json={"content": message}, timeout=5)
        return resp.status_code in (200, 204)
    except Exception:
        return False

def get_group_webhook(group_id: str, groups_df: pd.DataFrame) -> str:
    match = groups_df[groups_df["Group_ID"] == group_id]
    return str(match.iloc[0].get("Discord_Webhook", "")).strip() if not match.empty else ""

def get_user_dm_webhook(user_id: str, users_df: pd.DataFrame) -> str:
    match = users_df[users_df["User_ID"] == user_id]
    return str(match.iloc[0].get("Discord_Webhook_DM", "")).strip() if not match.empty else ""

def clean_and_parse_progress(val):
    if pd.isna(val) or val == "": return 0.0
    try: return float(str(val).replace("%", "").strip())
    except ValueError: return 0.0

def parse_deadline_timezone(dl_str: str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M"):
        try: return datetime.strptime(str(dl_str).strip(), fmt).replace(tzinfo=TZ)
        except ValueError: continue
    return None

def calculate_task_status(row: pd.Series) -> str:
    if str(row.get("Trạng_Thái", "")) == "Đã xong" or clean_and_parse_progress(row.get("Tiến_Độ_%")) == 100.0: return "done"
    dl = parse_deadline_timezone(row.get("Deadline", ""))
    if dl is None: return "unknown"
    diff_hours = (dl - NOW()).total_seconds() / 3600
    if diff_hours < 0: return "overdue"
    if diff_hours <= 24: return "urgent"
    return "safe"

def format_time_remaining(row: pd.Series) -> str:
    if str(row.get("Trạng_Thái", "")) == "Đã xong": return "Xong sạch rồi 🎉"
    dl = parse_deadline_timezone(row.get("Deadline", ""))
    if dl is None: return "—"
    total_seconds = int((dl - NOW()).total_seconds())
    if total_seconds < 0: return "ĐÃ QUÁ HẠN! 🛑"
    return f"⏳ Còn {total_seconds // 3600} giờ"

def get_user_name(user_id, users_df):
    match = users_df[users_df["User_ID"] == user_id]
    return match.iloc[0]["Tên"] if not match.empty else f"Ẩn danh ({user_id})"

def get_initials(name: str) -> str:
    parts = name.strip().split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()

def render_bubble(sender_name: str, content: str, time_str: str, is_me: bool, variant: str = "group") -> str:
    initials = get_initials(sender_name)
    cls = "msg-me" if is_me else ("msg-dm" if variant == "dm" else "msg-other")
    meta = time_str if is_me else f"{sender_name} · {time_str}"
    return f"""
<div class="msg-bubble {cls}">
  <div class="msg-avatar">{initials}</div>
  <div class="msg-body">
    <div class="msg-meta">{meta}</div>
    <div class="msg-text">{content}</div>
  </div>
</div>"""

def render_messages_html(rows_iter, my_id, users_df, variant="group") -> str:
    html = '<div class="chat-wrap">'
    prev_date = None
    for _, row in rows_iter:
        sender_name = get_user_name(row["Người_Gửi_ID"], users_df)
        is_me       = row["Người_Gửi_ID"] == my_id
        time_str    = str(row["Thời_Gian"])
        cur_date    = time_str[:10] if len(time_str) >= 10 else time_str
        if cur_date != prev_date:
            html += f'<div class="date-sep">{cur_date}</div>'
            prev_date = cur_date
        short_time = time_str[11:16] if len(time_str) >= 16 else time_str
        html += render_bubble(sender_name, str(row["Nội_Dung"]), short_time, is_me, variant)
    html += '</div>'
    return html

# ═══════════════════════════════════════════════════════════
#  5. AUTH SYSTEM
# ═══════════════════════════════════════════════════════════

def show_auth_page(data):
    users_df = data["users"]
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🛡️ DEADLINE SLAYER</h1>", unsafe_allow_html=True)
        tab_login, tab_reg = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký Tài Khoản"])
        with tab_login:
            log_id   = st.text_input("User ID (VD: U001)", key="log_id").strip()
            log_pass = st.text_input("Mật khẩu", type="password", key="log_pass")
            if st.button("🚀 Đăng Nhập", use_container_width=True, type="primary"):
                fetch_all_data.clear()
                fresh_users = fetch_all_data()["users"]
                user_match = fresh_users[(fresh_users["User_ID"] == log_id) & (fresh_users["Password"] == log_pass)] if not fresh_users.empty else pd.DataFrame()
                if not user_match.empty:
                    st.session_state['logged_in'] = True
                    st.session_state['current_user'] = user_match.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error(msg_login_fail())
        with tab_reg:
            reg_name  = st.text_input("Họ và Tên", key="reg_name").strip()
            reg_email = st.text_input("Email", key="reg_email").strip()
            reg_pass  = st.text_input("Mật khẩu", type="password", key="reg_pass")
            if st.button("✨ Tạo Tài Khoản", use_container_width=True):
                if not reg_name or not reg_email or not reg_pass: st.error("Vui lòng điền đủ thông tin!")
                else:
                    fresh_users = fetch_all_data()["users"]
                    if not fresh_users.empty and reg_email in fresh_users["Email"].values: st.error("Email đã tồn tại!")
                    else:
                        new_id = f"U{(len(fresh_users) + 1):03d}" if not fresh_users.empty else "U001"
                        append_row_data(WS_USERS, [new_id, reg_pass, reg_name, reg_email, "", "", NOW().strftime("%Y-%m-%d %H:%M:%S")])
                        st.success(msg_register_success(new_id))

# ═══════════════════════════════════════════════════════════
#  6. MAIN APP MAIN CONTROLLER
# ═══════════════════════════════════════════════════════════

def main_app(data):
    users_df, groups_df, tasks_df = data["users"], data["groups"], data["tasks"]
    current_user = st.session_state['current_user']
    my_id = current_user["User_ID"]
    is_leader = not groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id].empty

    with st.sidebar:
        st.markdown("## ⚔️ DEADLINE SLAYER")
        st.success(f"👤 **{current_user['Tên']}**\n\n🆔 ID: `{my_id}`")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state['logged_in'] = False
            st.session_state['current_user'] = None
            st.rerun()
        s_name = st.text_input("Tên Google Sheets", value=st.session_state["sheet_name"])
        if s_name != st.session_state["sheet_name"]:
            st.session_state["sheet_name"] = s_name
            fetch_all_data.clear()
            st.rerun()

    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📊 Dashboard Công Việc", "👥 Kết Bạn & Tạo Nhóm", "📋 Giao Việc Mới",
        "💬 Chat", "🏆 Xếp Hạng", "👥 Danh Sách Bạn Bè"
    ])

    me_in_db = users_df[users_df["User_ID"] == my_id].iloc[0] if not users_df[users_df["User_ID"] == my_id].empty else {"Bạn_Bè": ""}
    my_friends_list = [f.strip() for f in str(me_in_db.get("Bạn_Bè", "")).split(",") if f.strip()]

    with t1: render_dashboard(tasks_df, groups_df, users_df, my_id)
    with t2: render_network(users_df, groups_df, my_id, my_friends_list)
    with t3: render_assign_task(users_df, groups_df, tasks_df, my_id, my_friends_list)
    with t4: render_chat(data["chat"], data["dm"], groups_df, users_df, my_id, my_friends_list)
    with t5: render_leaderboard(tasks_df, users_df)
    with t6: render_friend_list(users_df, my_id, my_friends_list)

# ═══════════════════════════════════════════════════════════
#  7. RENDER SUB-FUNCTIONS
# ═══════════════════════════════════════════════════════════

def render_dashboard(tasks_df, groups_df, users_df, my_id):
    st.subheader("📊 Bảng Tiến Độ Công Việc")
    my_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False, case=False)]
    subordinates = []
    for _, grp in my_groups.iterrows():
        subordinates.extend([m.strip() for m in str(grp["Thành_Viên_IDs"]).split(",") if m.strip()])
    
    visible_tasks = tasks_df[(tasks_df["Người_Phụ_Trách_ID"] == my_id) | (tasks_df["Người_Phụ_Trách_ID"].isin(subordinates))].copy()
    if visible_tasks.empty:
        st.info("🎉 Trống trơn! Chưa có nhiệm vụ nào cả!")
        return

    visible_tasks["Tiến_Độ_%"] = visible_tasks["Tiến_Độ_%"].apply(clean_and_parse_progress)
    visible_tasks["_status"] = visible_tasks.apply(calculate_task_status, axis=1)
    visible_tasks["_remaining"] = visible_tasks.apply(format_time_remaining, axis=1)

    for _, row in visible_tasks.iterrows():
        b_color = {"done": "#2e7d32", "overdue": "#d32f2f", "urgent": "#f57c00", "safe": "#1976d2"}.get(row["_status"], "#cccccc")
        st.markdown(f"""
        <div style="border:1px solid {b_color}; border-left:5px solid {b_color}; background:#111112; border-radius:10px; padding:12px 16px; margin-bottom:8px;">
            <b>📌 {row['Tên_Công_Việc']}</b> | Người Phụ Trách: {get_user_name(row['Người_Phụ_Trách_ID'], users_df)} <br>
            <small>⏰ Hạn: {row['Deadline']} | {row['_remaining']} | Tiến độ: {row['Tiến_Độ_%']}%</small>
        </div>
        """, unsafe_allow_html=True)
        
        if row['Người_Phụ_Trách_ID'] == my_id:
            with st.expander("🛠 Cập nhật"):
                c1, c2 = st.columns(2)
                with c1:
                    np = st.slider("Tiến độ (%)", 0, 100, int(row["Tiến_Độ_%"]), key=f"sl_{row['ID']}")
                with c2:
                    ns = st.selectbox("Trạng thái", ["Chưa bắt đầu", "Đang làm", "Đã xong"], key=f"sb_{row['ID']}")
                if st.button("💾 Lưu Cập Nhật", key=f"btn_{row['ID']}"):
                    update_cell_by_id(WS_TASKS, "ID", row["ID"], "Tiến_Độ_%", f"{np}%", TASK_COLS)
                    update_cell_by_id(WS_TASKS, "ID", row["ID"], "Trạng_Thái", ns, TASK_COLS)
                    st.rerun()

def render_network(users_df, groups_df, my_id, my_friends_list):
    st.subheader("👥 Quản Lý Mạng Lưới Kết Nối")
    t_f, t_g = st.tabs(["🤝 Kết Bạn", "🏰 Tạo Nhóm"])
    with t_f:
        f_id = st.text_input("Nhập User ID muốn kết bạn:").strip()
        if st.button("🤝 Kết Bạn"):
            if f_id == my_id: st.error("Không thể kết bạn với chính mình!")
            elif f_id in my_friends_list: st.warning("Đã là bạn bè!")
            elif f_id not in users_df["User_ID"].values: st.error("Không tìm thấy ID người dùng!")
            else:
                my_friends_list.append(f_id)
                update_cell_by_id(WS_USERS, "User_ID", my_id, "Bạn_Bè", ",".join(my_friends_list), USER_COLS)
                
                their_row = users_df[users_df["User_ID"] == f_id].iloc[0]
                their_friends = [f.strip() for f in str(their_row.get("Bạn_Bè", "")).split(",") if f.strip()]
                if my_id not in their_friends:
                    their_friends.append(my_id)
                    update_cell_by_id(WS_USERS, "User_ID", f_id, "Bạn_Bè", ",".join(their_friends), USER_COLS)
                st.success(msg_friend_added(get_user_name(f_id, users_df)))
                st.rerun()
    with t_g:
        g_name = st.text_input("Tên nhóm mới:")
        g_wh = st.text_input("Discord Webhook Nhóm (Nếu có):")
        sel_m = st.multiselect("Thêm thành viên nhóm:", options=my_friends_list, format_func=lambda x: get_user_name(x, users_df))
        if st.button("🏰 Tạo nhóm"):
            if not g_name: st.error("Tên nhóm trống!")
            else:
                new_gid = f"G{(len(groups_df)+1):03d}"
                all_m = [my_id] + sel_m
                append_row_data(WS_GROUPS, [new_gid, g_name, my_id, ",".join(all_m), g_wh, NOW().strftime("%Y-%m-%d %H:%M:%S")])
                if g_wh: push_to_discord(discord_group_created(g_name), g_wh)
                st.success(msg_group_created(g_name))
                st.rerun()

def render_assign_task(users_df, groups_df, tasks_df, my_id, my_friends_list):
    st.subheader("📋 Giao Việc Mới")
    my_groups = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
    if my_groups.empty:
        st.info("💡 Bạn cần làm Trưởng Nhóm của một nhóm để thực hiện giao việc!")
        return
    g_opts = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in my_groups.iterrows()}
    sel_gid = st.selectbox("Chọn nhóm giao việc:", options=list(g_opts.keys()), format_func=lambda x: g_opts[x])
    
    t_name = st.text_input("Tên công việc:")
    t_sub = st.text_input("Môn học:")
    grp_row = my_groups[my_groups["Group_ID"] == sel_gid].iloc[0]
    grp_members = [m.strip() for m in str(grp_row["Thành_Viên_IDs"]).split(",") if m.strip()]
    
    sel_assignee = st.selectbox("Người phụ trách:", options=grp_members, format_func=lambda x: get_user_name(x, users_df))
    t_dl = st.date_input("Hạn chót:")
    
    if st.button("🚀 Phát Lệnh Giao Việc", type="primary"):
        if not t_name: st.error("Vui lòng điền tên việc!")
        else:
            new_tid = f"T{(len(tasks_df)+1):03d}"
            dl_str = f"{t_dl} 23:59:59"
            append_row_data(WS_TASKS, [new_tid, t_name, t_sub, sel_assignee, dl_str, "Trung bình", "Chưa bắt đầu", "0%", "Khởi động", "", "Không", "", NOW().strftime("%Y-%m-%d %H:%M:%S"), NOW().strftime("%Y-%m-%d %H:%M:%S")])
            wh = grp_row.get("Discord_Webhook", "")
            if wh: push_to_discord(discord_task_assigned(t_name, get_user_name(sel_assignee, users_df), dl_str, "Trung bình"), wh)
            st.success(msg_task_assigned(t_name, get_user_name(sel_assignee, users_df)))
            st.rerun()

def render_chat(chat_df, dm_df, groups_df, users_df, my_id, my_friends_list):
    st.subheader("💬 Trung Tâm Tin Nhắn")
    mode = st.radio("Chế độ:", ["🏰 Phòng Chat Nhóm", "📩 Chat Riêng (DM)"], horizontal=True)
    my_groups = groups_df[groups_df["Thành_Viên_IDs"].astype(str).str.contains(my_id, na=False, case=False)]

    if mode == "🏰 Phòng Chat Nhóm":
        if my_groups.empty:
            st.info("Bạn chưa tham gia nhóm nào cả!")
            return
        g_opts = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in my_groups.iterrows()}
        sel_gid = st.selectbox("Chọn nhóm trò chuyện:", options=list(g_opts.keys()), format_func=lambda x: g_opts[x])
        
        # SỬA LỖI LỌC TIN NHẮN WEB: Ép kiểu dữ liệu đồng nhất sang chuỗi string và loại bỏ khoảng trắng thừa
        f_chat = chat_df[chat_df["Group_Nhận_ID"].astype(str).str.strip() == str(sel_gid).strip()]
        
        if f_chat.empty: st.markdown('<div class="chat-empty">Chưa có tin nhắn nào tại nhóm này. Hãy mở lời trước nhé!</div>', unsafe_allow_html=True)
        else: st.markdown(render_messages_html(f_chat.iterrows(), my_id, users_df, variant="group"), unsafe_allow_html=True)
        
        with st.form("grp_form", clear_on_submit=True):
            txt = st.text_input("Nhập tin nhắn nhóm...")
            if st.form_submit_button("Gửi 🚀", use_container_width=True) and txt.strip():
                now_str = NOW().strftime("%Y-%m-%d %H:%M:%S")
                append_row_data(WS_CHAT, [now_str, my_id, sel_gid, txt.strip()])
                wh = get_group_webhook(sel_gid, groups_df)
                if wh: push_to_discord(discord_group_chat(get_user_name(my_id, users_df), g_opts[sel_gid], txt.strip()), wh)
                st.rerun()
    else:
        if not my_friends_list:
            st.info("Danh sách bạn bè trống!")
            return
        sel_fid = st.selectbox("Chọn bạn bè:", options=my_friends_list, format_func=lambda x: get_user_name(x, users_df))
        
        # Ép kiểu và xóa khoảng trắng cho DM để hiển thị chính xác
        f_dm = dm_df[
            ((dm_df["Người_Gửi_ID"].astype(str).str.strip() == my_id) & (dm_df["Người_Nhận_ID"].astype(str).str.strip() == str(sel_fid).strip())) |
            ((dm_df["Người_Gửi_ID"].astype(str).str.strip() == str(sel_fid).strip()) & (dm_df["Người_Nhận_ID"].astype(str).str.strip() == my_id))
        ]
        
        if f_dm.empty: st.markdown('<div class="chat-empty">Chưa có cuộc hội thoại nào. Hãy gửi lời chào!</div>', unsafe_allow_html=True)
        else: st.markdown(render_messages_html(f_dm.iterrows(), my_id, users_df, variant="dm"), unsafe_allow_html=True)
        
        with st.form("dm_form", clear_on_submit=True):
            txt = st.text_input("Nhập tin nhắn riêng...")
            if st.form_submit_button("Gửi 🚀", use_container_width=True) and txt.strip():
                now_str = NOW().strftime("%Y-%m-%d %H:%M:%S")
                append_row_data(WS_DM, [now_str, my_id, sel_fid, txt.strip()])
                wh = get_user_dm_webhook(sel_fid, users_df)
                if wh: push_to_discord(discord_dm(get_user_name(my_id, users_df), txt.strip()), wh)
                st.rerun()

def render_leaderboard(tasks_df, users_df):
    st.subheader("🏆 Bảng Xếp Hạng Diệt Deadline")
    done_tasks = tasks_df[(tasks_df["Trạng_Thái"] == "Đã xong") | (tasks_df["Tiến_Độ_%"].apply(clean_and_parse_progress) == 100.0)]
    if done_tasks.empty:
        st.info("Chưa có ai hoàn thành công việc nào.")
        return
    counts = done_tasks["Người_Phụ_Trách_ID"].value_counts().to_dict()
    arr = [{"Chiến binh": get_user_name(uid, users_df), "Nhiệm vụ đã diệt": c} for uid, c in counts.items()]
    st.table(pd.DataFrame(arr))

# ─── THAY THẾ TẬP TRUNG: DANH SÁCH BẠN BÈ & HỦY KẾT BẠN ──────
def render_friend_list(users_df, my_id, my_friends_list):
    st.subheader("👥 Danh Sách Bạn Bè")
    st.markdown("Dưới đây là danh sách toàn bộ đồng đội cày deadline của bạn. Bạn có thể chọn hủy kết bạn nếu cần thiết.")
    
    if not my_friends_list:
        st.info("Danh sách của bạn đang trống trơn. Hãy kết bạn mới ở mục 'Kết Bạn & Tạo Nhóm' nhé!")
        return

    for f_id in my_friends_list:
        f_name = get_user_name(f_id, users_df)
        f_email = "Không rõ Email"
        match = users_df[users_df["User_ID"] == f_id]
        if not match.empty:
            f_email = match.iloc[0].get("Email", "Không rõ Email")

        c_info, c_action = st.columns([4, 1])
        with c_info:
            st.markdown(f"🔹 **{f_name}** (ID: `{f_id}`) <br> <small style='color: gray;'>Email: {f_email}</small>", unsafe_allow_html=True)
        with c_action:
            # Nút hủy kết bạn tương ứng với từng ID bạn bè
            if st.button("❌ Hủy Kết Bạn", key=f"unf_{f_id}", use_container_width=True):
                # 1. Xóa người đó khỏi danh sách của mình
                my_updated = [f for f in my_friends_list if f != f_id]
                update_cell_by_id(WS_USERS, "User_ID", my_id, "Bạn_Bè", ",".join(my_updated), USER_COLS)
                
                # 2. Xóa mình khỏi danh sách bạn bè của người đó (Hủy kết bạn 2 chiều)
                if not match.empty:
                    their_friends = [f.strip() for f in str(match.iloc[0].get("Bạn_Bè", "")).split(",") if f.strip()]
                    their_updated = [f for f in their_friends if f != my_id]
                    update_cell_by_id(WS_USERS, "User_ID", f_id, "Bạn_Bè", ",".join(their_updated), USER_COLS)
                
                st.toast(f"✂️ Đã hủy kết bạn với {f_name} thành công!")
                fetch_all_data.clear()
                st.rerun()
        st.markdown("<hr style='margin: 8px 0; opacity: 0.1;'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  8. EXECUTION ENTRYPOINT
# ═══════════════════════════════════════════════════════════
data = fetch_all_data()
if not st.session_state['logged_in']:
    show_auth_page(data)
else:
    main_app(data)