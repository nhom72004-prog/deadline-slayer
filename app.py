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

.msg-bubble { display: flex; align-items: flex-end; gap: 8px; max-width: 85%; margin-bottom: 5px; }

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

/* Discord badge */
.disc-badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 12px; padding: 3px 10px; border-radius: 20px; font-weight: 600; margin-bottom: 4px;
}
.disc-on  { background: #e8f5e9; color: #2e7d32; }
.disc-off { background: #f0f0f0; color: #888; }
@media (prefers-color-scheme: dark) {
    .disc-on  { background: #1b3a1d; color: #81c784; }
    .disc-off { background: #2a2a2a; color: #777; }
}
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
#  2. LỜI NHẮN VUI VẺ
# ═══════════════════════════════════════════════════════════

def msg_login_success(name): return f"⚔️ Chào chiến binh **{name}**! Deadline đang run rẩy trước sự hiện diện của bạn!"
def msg_login_fail(): return "❌ Không tìm thấy tài khoản này! Kiểm tra lại ID và mật khẩu nhé bro~"
def msg_register_success(new_id): return f"🎉 WELCOME TO THE SQUAD! ID của bạn là **`{new_id}`** — nhớ kỹ nhé!"
def msg_task_assigned(task_name, assignee_name): return f"🚀 Lệnh đã ban! **{assignee_name}** vừa nhận nhiệm vụ **{task_name}**!"
def msg_progress_saved(percent): return f"⚡ {percent}%! Đã lưu tiến độ!"
def msg_friend_added(name): return f"🤝 **{name}** đã vào danh sách bạn bè!"
def msg_group_created(grp_name): return f"🏰 Nhóm **{grp_name}** đã được thành lập!"
def msg_webhook_saved(): return "🤖 Discord Webhook đã được kết nối!"

def msg_discord_broadcast(leader_name): return f"📢 **[THÔNG BÁO TỪ TRƯỞNG NHÓM {leader_name.upper()}]** 🔴\n"

def discord_task_assigned(task_name, assignee_name, deadline, priority):
    prio_map = {"Cao": "🔴 KHẨN CẤP", "Trung bình": "🟡 Bình thường", "Thấp": "🟢 Thư thả"}
    return (
        f"🚨 **NHIỆM VỤ MỚI XUẤT HIỆN!** 🚨\n"
        f"📌 **{task_name}**\n"
        f"👤 Chiến binh được chọn: **{assignee_name}**\n"
        f"⏰ Hạn chót: `{deadline}`\n"
        f"🏷️ Độ ưu tiên: {prio_map.get(priority, priority)}\n"
        f"💪 *Cố lên nào!*"
    )

def discord_group_chat(sender_name, group_label, content):
    return f"💬 **{sender_name}** › [{group_label}]:\n{content}"

def discord_dm_chat(sender_name, content):
    return f"📩 **Tin nhắn riêng từ {sender_name}:**\n{content}"

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
        "tasks":  pd.DataFrame(columns=TASK_COLS),
        "users":  pd.DataFrame(columns=USER_COLS),
        "groups": pd.DataFrame(columns=GROUP_COLS),
        "proofs": pd.DataFrame(columns=PROOF_COLS),
        "chat":   pd.DataFrame(columns=CHAT_COLS),
        "dm":     pd.DataFrame(columns=DM_COLS),
    }
    if not client: return empty_dict
    try:
        ss = client.open(st.session_state["sheet_name"])
        init_spreadsheet_structure(ss)
        def get_df(name, cols):
            all_vals = ss.worksheet(name).get_all_values()
            if not all_vals or len(all_vals) <= 1: return pd.DataFrame(columns=cols)
            df = pd.DataFrame(all_vals[1:], columns=all_vals[0])
            df = df.loc[:, ~df.columns.duplicated()]
            if "" in df.columns: df = df.drop(columns=[""])
            return df.reindex(columns=cols).fillna("")
        return {
            "tasks":  get_df(WS_TASKS,  TASK_COLS),
            "users":  get_df(WS_USERS,  USER_COLS),
            "groups": get_df(WS_GROUPS, GROUP_COLS),
            "proofs": get_df(WS_PROOFS, PROOF_COLS),
            "chat":   get_df(WS_CHAT,   CHAT_COLS),
            "dm":     get_df(WS_DM,     DM_COLS),
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
        st.error(f"💀 Ôi thôi, lỗi đồng bộ rồi: {e}")

# ═══════════════════════════════════════════════════════════
#  4. DISCORD & HELPERS
# ═══════════════════════════════════════════════════════════

def push_to_discord(message: str, webhook_url: str = "", file_bytes=None, filename: str = None) -> bool:
    if not webhook_url or "discord.com/api/webhooks" not in webhook_url: return False
    try:
        if file_bytes and filename:
            resp = requests.post(webhook_url, data={"content": message}, files={"file": (filename, file_bytes)}, timeout=15)
        else:
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
    if diff_hours < 0:   return "overdue"
    if diff_hours <= 24: return "urgent"
    if diff_hours <= 72: return "warning"
    return "safe"

def format_time_remaining(row: pd.Series) -> str:
    if str(row.get("Trạng_Thái", "")) == "Đã xong": return "Xong sạch rồi 🎉"
    dl = parse_deadline_timezone(row.get("Deadline", ""))
    if dl is None: return "—"
    total_seconds = int((dl - NOW()).total_seconds())
    if total_seconds < 0: return "ĐÃ QUÁ HẠN! Chạy ngay đi 🛑"
    days, rem  = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0: return f"⏳ Còn {days} ngày {hours} giờ"
    if hours > 0: return f"🚨 Chỉ còn {hours} giờ {minutes} phút"
    return f"💀 Chỉ còn {minutes} phút!!!"

def get_user_name(user_id, users_df):
    match = users_df[users_df["User_ID"] == user_id]
    return match.iloc[0]["Tên"] if not match.empty else f"Ẩn danh ({user_id})"

# ─── Chat UI helpers ──────────────────────────────────────

def get_initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2: return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if len(name) >= 2 else name.upper()

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
            st.subheader("Đăng nhập hệ thống")
            log_id   = st.text_input("User ID (VD: U001)", key="log_id").strip()
            log_pass = st.text_input("Mật khẩu", type="password", key="log_pass")
            if st.button("🚀 Đăng Nhập", use_container_width=True, type="primary"):
                fetch_all_data.clear()
                fresh_users = fetch_all_data()["users"]
                user_match = fresh_users[(fresh_users["User_ID"] == log_id) & (fresh_users["Password"] == log_pass)]
                if not user_match.empty:
                    st.session_state['logged_in']    = True
                    st.session_state['current_user'] = user_match.iloc[0].to_dict()
                    st.success(msg_login_success(user_match.iloc[0]["Tên"]))
                    st.rerun()
                else:
                    st.error(msg_login_fail())

        with tab_reg:
            st.subheader("Tạo tài khoản mới")
            reg_name  = st.text_input("Họ và Tên",  key="reg_name").strip()
            reg_email = st.text_input("Email",       key="reg_email").strip()
            reg_pass  = st.text_input("Mật khẩu",   type="password", key="reg_pass")
            reg_wh_dm = st.text_input("🤖 Discord Webhook cá nhân (tuỳ chọn):", key="reg_wh_dm").strip()
            if st.button("✨ Tạo Tài Khoản", use_container_width=True):
                if not reg_name or not reg_email or not reg_pass:
                    st.error("🙏 Điền đủ thông tin giúp mình với nha!")
                else:
                    fetch_all_data.clear()
                    fresh_users = fetch_all_data()["users"]
                    if not fresh_users.empty and reg_email in fresh_users["Email"].values:
                        st.error("📧 Email này đã có người dùng rồi!")
                    else:
                        new_id = "U001"
                        if not fresh_users.empty:
                            ids  = fresh_users["User_ID"].dropna().astype(str).tolist()
                            nums = [int(i[1:]) for i in ids if i.startswith("U") and i[1:].isdigit()]
                            new_id = f"U{(max(nums) + 1 if nums else 1):03d}"
                        append_row_data(WS_USERS, [new_id, reg_pass, reg_name, reg_email, "", reg_wh_dm, NOW().strftime("%Y-%m-%d %H:%M:%S")])
                        st.success(msg_register_success(new_id))

# ═══════════════════════════════════════════════════════════
#  6. TABS & FEATURES
# ═══════════════════════════════════════════════════════════

def render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader):
    st.subheader("📊 Bảng Tiến Độ Cá Nhân & Nhóm")
    my_groups    = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
    subordinates = []
    for _, grp in my_groups.iterrows():
        subordinates.extend([m.strip() for m in str(grp["Thành_Viên_IDs"]).split(",") if m.strip()])

    visible_tasks = tasks_df[
        (tasks_df["Người_Phụ_Trách_ID"] == my_id) |
        (tasks_df["Người_Phụ_Trách_ID"].isin(subordinates))
    ].copy()

    if visible_tasks.empty:
        st.info("🎉 Trống trơn! Chưa có nhiệm vụ nào cả!")
        return

    visible_tasks["Tiến_Độ_%"] = visible_tasks["Tiến_Độ_%"].apply(clean_and_parse_progress)
    visible_tasks["_status"]   = visible_tasks.apply(calculate_task_status, axis=1)
    visible_tasks["_remaining"] = visible_tasks.apply(format_time_remaining, axis=1)

    status_labels = {
        "done": "✅ XONG RỒI", "overdue": "💀 QUÁ HẠN",
        "urgent": "🔥 KHẨN CẤP", "warning": "⚠️ SẮP ĐẾN HẠN",
        "safe": "😎 CÒN THỜI GIAN", "unknown": "❓ KHÔNG RÕ",
    }

    for _, row in visible_tasks.iterrows():
        b_color = {
            "done": "#2e7d32", "overdue": "#d32f2f",
            "urgent": "#f57c00", "warning": "#fbc02d", "safe": "#1976d2"
        }.get(row["_status"], "#cccccc")
        assignee_name = get_user_name(row['Người_Phụ_Trách_ID'], users_df)
        status_label  = status_labels.get(row["_status"], row["_status"].upper())

        st.markdown(f"""
        <div style="border:1px solid {b_color}; border-left:5px solid {b_color}; background:#111112;
             border-radius:10px; padding:12px 16px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between;">
                <b>📌 {row['Tên_Công_Việc']}</b>
                <span style="color:{b_color}; font-weight:bold;">{status_label}</span>
            </div>
            <div style="font-size:13px; color:#aaa; margin-top:5px;">
                👤 Phụ trách: <b>{assignee_name}</b> | ⏰ Hạn: {row['Deadline']}
            </div>
            <div style="font-size:14px; color:{b_color}; font-weight:500; margin-top:3px;">
                {row['_remaining']} | Tiến độ: {row['Tiến_Độ_%']}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        if row['Người_Phụ_Trách_ID'] == my_id:
            with st.expander("🛠 Cập nhật & Nộp Minh Chứng"):
                c1, c2 = st.columns(2)
                with c1:
                    new_prog = st.number_input("Tiến độ (%)", 0, 100, int(row['Tiến_Độ_%']), key=f"prog_{row['ID']}")
                with c2:
                    new_phase = st.text_input("Giai đoạn hiện tại", str(row['Giai_Đoạn_Hiện_Tại']), key=f"phase_{row['ID']}")
                
                if st.button("💾 Lưu Cập Nhật", key=f"btn_{row['ID']}", use_container_width=True):
                    update_cell_by_id(WS_TASKS, "ID", row['ID'], "Tiến_Độ_%", f"{new_prog}%", TASK_COLS)
                    update_cell_by_id(WS_TASKS, "ID", row['ID'], "Giai_Đoạn_Hiện_Tại", new_phase, TASK_COLS)
                    if new_prog == 100:
                        update_cell_by_id(WS_TASKS, "ID", row['ID'], "Trạng_Thái", "Đã xong", TASK_COLS)
                    fetch_all_data.clear()
                    st.toast(msg_progress_saved(new_prog))
                    st.rerun()

def render_network(users_df, groups_df, my_id, my_friends_list):
    st.subheader("👥 Thêm Bạn & Nhóm")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🤝 Thêm bạn bè**")
        friend_id = st.text_input("Nhập User ID để kết bạn (VD: U002)").strip()
        if st.button("Kết Bạn", use_container_width=True):
            if friend_id == my_id:
                st.warning("Không thể tự kết bạn với chính mình!")
            elif friend_id in my_friends_list:
                st.info("Người này đã là bạn của bạn rồi!")
            elif friend_id in users_df["User_ID"].values:
                my_friends_list.append(friend_id)
                update_cell_by_id(WS_USERS, "User_ID", my_id, "Bạn_Bè", ",".join(my_friends_list), USER_COLS)
                
                # Bi-directional friendship
                their_row = users_df[users_df["User_ID"] == friend_id].iloc[0]
                their_friends = [x.strip() for x in str(their_row["Bạn_Bè"]).split(",") if x.strip()]
                if my_id not in their_friends:
                    their_friends.append(my_id)
                    update_cell_by_id(WS_USERS, "User_ID", friend_id, "Bạn_Bè", ",".join(their_friends), USER_COLS)
                
                fetch_all_data.clear()
                st.success(f"Đã thêm {get_user_name(friend_id, users_df)} vào danh sách bạn bè!")
                st.rerun()
            else:
                st.error("Không tìm thấy User ID này!")

    with col2:
        st.markdown("**🏰 Tạo Nhóm Mới**")
        grp_name = st.text_input("Tên nhóm mới")
        grp_members = st.multiselect("Chọn thành viên (từ danh sách bạn bè)", my_friends_list, format_func=lambda x: get_user_name(x, users_df))
        if st.button("Tạo Nhóm", use_container_width=True):
            if grp_name and grp_members:
                new_grp_id = f"G{len(groups_df) + 1:03d}"
                all_mems = [my_id] + grp_members
                append_row_data(WS_GROUPS, [new_grp_id, grp_name, my_id, ",".join(all_mems), "", NOW().strftime("%Y-%m-%d %H:%M:%S")])
                st.success(f"Đã tạo nhóm {grp_name}!")
                st.rerun()
            else:
                st.warning("Vui lòng nhập tên nhóm và chọn ít nhất 1 thành viên!")

def render_assign_task(users_df, groups_df, tasks_df, my_id, my_friends_list):
    st.subheader("📋 Giao Việc Mới")
    my_groups = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
    
    if my_groups.empty and not my_friends_list:
        st.info("Bạn cần tạo nhóm hoặc kết bạn trước khi có thể giao việc!")
        return

    assign_to = st.radio("Đối tượng nhận việc", ["Thành viên nhóm", "Bạn bè độc lập"])
    
    target_id = ""
    if assign_to == "Thành viên nhóm":
        if my_groups.empty: st.warning("Bạn chưa làm trưởng nhóm của nhóm nào.")
        else:
            grp_opts = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in my_groups.iterrows()}
            sel_grp = st.selectbox("Chọn nhóm", list(grp_opts.keys()), format_func=lambda x: grp_opts[x])
            mems = [m.strip() for m in str(groups_df[groups_df["Group_ID"] == sel_grp].iloc[0]["Thành_Viên_IDs"]).split(",") if m.strip()]
            target_id = st.selectbox("Chọn thành viên", mems, format_func=lambda x: get_user_name(x, users_df))
    else:
        target_id = st.selectbox("Chọn bạn bè", my_friends_list, format_func=lambda x: get_user_name(x, users_df))

    task_name = st.text_input("Tên công việc")
    deadline = st.date_input("Hạn chót (Ngày)")
    time_dl = st.time_input("Hạn chót (Giờ)")
    priority = st.selectbox("Độ ưu tiên", ["Cao", "Trung bình", "Thấp"])
    
    if st.button("🚀 Giao Việc", use_container_width=True, type="primary"):
        if task_name and target_id:
            new_task_id = f"T{len(tasks_df) + 1:04d}"
            dl_str = f"{deadline.strftime('%Y-%m-%d')} {time_dl.strftime('%H:%M:%S')}"
            append_row_data(WS_TASKS, [
                new_task_id, task_name, "", target_id, dl_str, priority, 
                "Chưa bắt đầu", "0%", "Khởi tạo", "", "", "", 
                NOW().strftime("%Y-%m-%d %H:%M:%S"), ""
            ])
            
            # Discord Notification
            if assign_to == "Thành viên nhóm":
                grp_wh = get_group_webhook(sel_grp, groups_df)
                if grp_wh: push_to_discord(discord_task_assigned(task_name, get_user_name(target_id, users_df), dl_str, priority), webhook_url=grp_wh)
            
            st.success(f"Đã giao việc '{task_name}' cho {get_user_name(target_id, users_df)}!")
            st.rerun()

def render_chat(chat_df, dm_df, groups_df, users_df, my_id, my_friends_list):
    st.subheader("💬 Trò Chuyện Hệ Thống (Real-time)")
    chat_type = st.radio("Chế độ Chat", ["Nhóm", "Cá nhân (DM)"], horizontal=True)

    if chat_type == "Nhóm":
        my_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False)]
        if my_groups.empty:
            st.info("Bạn chưa tham gia nhóm nào!")
            return
        
        grp_opts = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in my_groups.iterrows()}
        sel_grp = st.selectbox("Chọn nhóm", list(grp_opts.keys()), format_func=lambda x: grp_opts[x])
        
        # Filter and render
        messages = chat_df[chat_df["Group_Nhận_ID"] == sel_grp].sort_values("Thời_Gian")
        msg_html = render_messages_html(messages.iterrows(), my_id, users_df, "group") if not messages.empty else "<div class='chat-empty'>Chưa có tin nhắn nào. Mở bát đi!</div>"
        
        # Display Box
        st.markdown(f"<div style='height: 400px; overflow-y: auto; background: #1a1a1a; padding: 10px; border-radius: 10px; margin-bottom: 15px;'>{msg_html}</div>", unsafe_allow_html=True)

        with st.form("chat_form_group", clear_on_submit=True):
            cols = st.columns([5, 1])
            new_msg = cols[0].text_input("Nhập tin nhắn...", label_visibility="collapsed")
            if cols[1].form_submit_button("Gửi 🚀", use_container_width=True) and new_msg.strip():
                append_row_data(WS_CHAT, [NOW().strftime("%Y-%m-%d %H:%M:%S"), my_id, sel_grp, new_msg.strip()])
                grp_wh = get_group_webhook(sel_grp, groups_df)
                if grp_wh:
                    push_to_discord(discord_group_chat(get_user_name(my_id, users_df), grp_opts[sel_grp], new_msg.strip()), webhook_url=grp_wh)
                fetch_all_data.clear()
                st.rerun()

    else:
        if not my_friends_list:
            st.info("Chưa có bạn bè để nhắn tin!")
            return
        sel_friend = st.selectbox("Chọn bạn bè", my_friends_list, format_func=lambda x: get_user_name(x, users_df))
        
        messages = dm_df[
            ((dm_df["Người_Gửi_ID"] == my_id) & (dm_df["Người_Nhận_ID"] == sel_friend)) |
            ((dm_df["Người_Gửi_ID"] == sel_friend) & (dm_df["Người_Nhận_ID"] == my_id))
        ].sort_values("Thời_Gian")
        
        msg_html = render_messages_html(messages.iterrows(), my_id, users_df, "dm") if not messages.empty else "<div class='chat-empty'>Gửi lời chào đi nào!</div>"
        
        st.markdown(f"<div style='height: 400px; overflow-y: auto; background: #1a1a1a; padding: 10px; border-radius: 10px; margin-bottom: 15px;'>{msg_html}</div>", unsafe_allow_html=True)

        with st.form("chat_form_dm", clear_on_submit=True):
            cols = st.columns([5, 1])
            new_msg = cols[0].text_input("Nhập tin nhắn riêng...", label_visibility="collapsed")
            if cols[1].form_submit_button("Gửi 📩", use_container_width=True) and new_msg.strip():
                append_row_data(WS_DM, [NOW().strftime("%Y-%m-%d %H:%M:%S"), my_id, sel_friend, new_msg.strip()])
                dm_wh = get_user_dm_webhook(sel_friend, users_df)
                if dm_wh:
                    push_to_discord(discord_dm_chat(get_user_name(my_id, users_df), new_msg.strip()), webhook_url=dm_wh)
                fetch_all_data.clear()
                st.rerun()

def render_leaderboard(tasks_df, users_df):
    st.subheader("🏆 Xếp Hạng Năng Suất")
    if tasks_df.empty:
        st.info("Chưa có dữ liệu để xếp hạng!")
        return
    
    # Calculate completed tasks per user
    completed = tasks_df[tasks_df["Trạng_Thái"] == "Đã xong"]
    if completed.empty:
        st.info("Chưa có ai hoàn thành nhiệm vụ nào cả!")
        return

    counts = completed["Người_Phụ_Trách_ID"].value_counts().reset_index()
    counts.columns = ["User_ID", "Số_Task_Hoàn_Thành"]
    counts["Tên"] = counts["User_ID"].apply(lambda x: get_user_name(x, users_df))
    
    st.dataframe(counts[["Tên", "Số_Task_Hoàn_Thành"]], use_container_width=True, hide_index=True)

def render_friend_management(users_df, my_id, my_friends_list):
    st.subheader("👥 Quản Lý Bạn Bè (Hủy Kết Bạn)")
    
    if not my_friends_list:
        st.info("Danh sách bạn bè trống. Hãy kết bạn ở tab 'Kết Bạn & Tạo Nhóm' nhé!")
        return
        
    st.write("Dưới đây là danh sách bạn bè hiện tại của bạn. Bạn có thể xóa liên kết bất cứ lúc nào.")
    
    for f_id in my_friends_list:
        f_name = get_user_name(f_id, users_df)
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"👤 **{f_name}** (`{f_id}`)")
        with c2:
            if st.button("❌ Hủy kết bạn", key=f"unfriend_{f_id}", use_container_width=True):
                # Remove from my list
                my_friends_list.remove(f_id)
                update_cell_by_id(WS_USERS, "User_ID", my_id, "Bạn_Bè", ",".join(my_friends_list), USER_COLS)
                
                # Remove me from their list
                their_row = users_df[users_df["User_ID"] == f_id]
                if not their_row.empty:
                    their_friends = [x.strip() for x in str(their_row.iloc[0]["Bạn_Bè"]).split(",") if x.strip()]
                    if my_id in their_friends:
                        their_friends.remove(my_id)
                        update_cell_by_id(WS_USERS, "User_ID", f_id, "Bạn_Bè", ",".join(their_friends), USER_COLS)
                
                fetch_all_data.clear()
                st.toast(f"Đã hủy kết bạn với {f_name}")
                st.rerun()

# ═══════════════════════════════════════════════════════════
#  7. MAIN EXECUTOR
# ═══════════════════════════════════════════════════════════

def main_app(data):
    users_df     = data["users"]
    groups_df    = data["groups"]
    tasks_df     = data["tasks"]
    current_user = st.session_state['current_user']
    my_id        = current_user["User_ID"]
    is_leader    = not groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id].empty

    with st.sidebar:
        st.markdown("## ⚔️ DEADLINE SLAYER")
        st.markdown("---")
        st.success(f"👤 **{current_user['Tên']}**\n\n🆔 ID: `{my_id}`")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state['logged_in']    = False
            st.session_state['current_user'] = None
            st.rerun()

        st.markdown("---")
        st.markdown("### 🔔 Discord Webhook Cá Nhân")
        my_row    = users_df[users_df["User_ID"] == my_id]
        cur_wh_dm = str(my_row.iloc[0].get("Discord_Webhook_DM", "")).strip() if not my_row.empty else ""
        new_wh_dm = st.text_input("Webhook nhận DM của bạn:", value=cur_wh_dm, placeholder="https://discord.com/api/...", key="sidebar_wh_dm").strip()
        if st.button("💾 Lưu Webhook DM", use_container_width=True):
            update_cell_by_id(WS_USERS, "User_ID", my_id, "Discord_Webhook_DM", new_wh_dm, USER_COLS)
            st.toast(msg_webhook_saved())

    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📊 Dashboard Công Việc",
        "👥 Kết Bạn & Tạo Nhóm",
        "📋 Giao Việc Mới",
        "💬 Chat",
        "🏆 Xếp Hạng",
        "👥 Quản Lý Bạn Bè", 
    ])

    me_in_db        = users_df[users_df["User_ID"] == my_id].iloc[0]
    my_friends_list = [f.strip() for f in str(me_in_db["Bạn_Bè"]).split(",") if f.strip()]

    with t1: render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader)
    with t2: render_network(users_df, groups_df, my_id, my_friends_list)
    with t3: render_assign_task(users_df, groups_df, tasks_df, my_id, my_friends_list)
    with t4: render_chat(data["chat"], data["dm"], groups_df, users_df, my_id, my_friends_list)
    with t5: render_leaderboard(tasks_df, users_df)
    with t6: render_friend_management(users_df, my_id, my_friends_list)

# ENTRY POINT
if __name__ == "__main__":
    app_data = fetch_all_data()
    if not st.session_state['logged_in']:
        show_auth_page(app_data)
    else:
        main_app(app_data)