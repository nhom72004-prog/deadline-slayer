import streamlit as st
from datetime import datetime
import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from zoneinfo import ZoneInfo
import json
import os

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
.chat-card {
    background: #1e1f22; border-radius: 8px; padding: 10px 14px;
    margin-bottom: 8px; border: 1px solid #2b2d31;
}
.chat-private {
    background: #1a233a; border-radius: 8px; padding: 10px 14px;
    margin-bottom: 8px; border: 1px solid #3b4898;
}
.chat-me {
    background: #1a2e1a; border-radius: 8px; padding: 10px 14px;
    margin-bottom: 8px; border: 1px solid #2d6a2d;
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
WS_DM     = "DirectMessages"   # ← SHEET MỚI cho tin nhắn cá nhân

TASK_COLS  = ["ID", "Tên_Công_Việc", "Môn_Học", "Người_Phụ_Trách_ID", "Deadline",
              "Độ_Ưu_Tiên", "Trạng_Thái", "Tiến_Độ_%", "Giai_Đoạn_Hiện_Tại",
              "Ghi_Chú", "Nhắc_Mỗi_Phút", "Nhắc_Lần_Cuối", "Ngày_Tạo", "Ngày_Cập_Nhật"]
USER_COLS  = ["User_ID", "Password", "Tên", "Email", "Bạn_Bè", "Discord_Webhook_DM", "Ngày_Tạo"]
GROUP_COLS = ["Group_ID", "Tên_Nhóm", "Trưởng_Nhóm_ID", "Thành_Viên_IDs", "Discord_Webhook", "Ngày_Tạo"]
PROOF_COLS = ["Task_ID", "Người_Nộp_ID", "Thời_Gian", "Mô_Tả", "Giai_Đoạn", "URL_File"]
CHAT_COLS  = ["Thời_Gian", "Người_Gửi_ID", "Group_Nhận_ID", "Nội_Dung"]
DM_COLS    = ["Thời_Gian", "Người_Gửi_ID", "Người_Nhận_ID", "Nội_Dung"]  # ← Schema DM

# ═══════════════════════════════════════════════════════════
#  2. GOOGLE SHEETS CORE FUNCTIONS
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
        WS_TASKS:  TASK_COLS,
        WS_USERS:  USER_COLS,
        WS_GROUPS: GROUP_COLS,
        WS_PROOFS: PROOF_COLS,
        WS_CHAT:   CHAT_COLS,
        WS_DM:     DM_COLS,
    }
    for name, cols in schemas.items():
        if name not in existing:
            ws = ss.add_worksheet(title=name, rows=1000, cols=len(cols))
            ws.append_row(cols)

@st.cache_data(ttl=3)
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
            if "" in df.columns:
                df = df.drop(columns=[""])
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
    if not client:
        return None
    try:
        return client.open(st.session_state["sheet_name"]).worksheet(name)
    except Exception:
        return None

def append_row_data(name: str, row: list):
    ws = get_worksheet_target(name)
    if ws:
        ws.append_row(row, value_input_option="USER_ENTERED")
        fetch_all_data.clear()

def update_cell_by_id(ws_name, id_col_name, item_id, update_col_name, new_val, schema_cols):
    ws = get_worksheet_target(ws_name)
    if not ws:
        return
    try:
        id_col_idx     = schema_cols.index(id_col_name) + 1
        update_col_idx = schema_cols.index(update_col_name) + 1
        cell = ws.find(str(item_id))
        if cell and cell.col == id_col_idx:
            ws.update_cell(cell.row, update_col_idx, new_val)
            fetch_all_data.clear()
    except Exception as e:
        st.error(f"Lỗi đồng bộ: {e}")

def delete_row_by_id(ws_name, id_col_name, item_id, schema_cols):
    ws = get_worksheet_target(ws_name)
    if not ws:
        return False
    try:
        id_col_idx = schema_cols.index(id_col_name) + 1
        cell = ws.find(str(item_id))
        if cell and cell.col == id_col_idx:
            ws.delete_rows(cell.row)
            fetch_all_data.clear()
            return True
        return False
    except Exception as e:
        st.error(f"Lỗi xóa: {e}")
        return False

# ═══════════════════════════════════════════════════════════
#  3. DISCORD & HELPERS
# ═══════════════════════════════════════════════════════════

def push_to_discord(message: str, webhook_url: str = "", file_bytes=None, filename: str = None) -> bool:
    if not webhook_url or "discord.com/api/webhooks" not in webhook_url:
        return False
    try:
        if file_bytes and filename:
            data = {"content": message}
            files = {"file": (filename, file_bytes)}
            resp = requests.post(webhook_url, data=data, files=files, timeout=15)
        else:
            resp = requests.post(webhook_url, json={"content": message}, timeout=5)
        return resp.status_code in (200, 204)
    except Exception as e:
        st.warning(f"Lỗi khi gửi Discord: {str(e)}")
        return False

def get_group_webhook(group_id: str, groups_df: pd.DataFrame) -> str:
    match = groups_df[groups_df["Group_ID"] == group_id]
    if match.empty:
        return ""
    return str(match.iloc[0].get("Discord_Webhook", "")).strip()

def get_user_dm_webhook(user_id: str, users_df: pd.DataFrame) -> str:
    """Lấy Discord Webhook DM cá nhân của một user."""
    match = users_df[users_df["User_ID"] == user_id]
    if match.empty:
        return ""
    return str(match.iloc[0].get("Discord_Webhook_DM", "")).strip()

def clean_and_parse_progress(val):
    if pd.isna(val) or val == "":
        return 0.0
    try:
        return float(str(val).replace("%", "").strip())
    except ValueError:
        return 0.0

def parse_deadline_timezone(dl_str: str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(str(dl_str).strip(), fmt).replace(tzinfo=TZ)
        except ValueError:
            continue
    return None

def calculate_task_status(row: pd.Series) -> str:
    if str(row.get("Trạng_Thái", "")) == "Đã xong" or clean_and_parse_progress(row.get("Tiến_Độ_%")) == 100.0:
        return "done"
    dl = parse_deadline_timezone(row.get("Deadline", ""))
    if dl is None:
        return "unknown"
    diff_hours = (dl - NOW()).total_seconds() / 3600
    if diff_hours < 0:   return "overdue"
    if diff_hours <= 24: return "urgent"
    if diff_hours <= 72: return "warning"
    return "safe"

def format_time_remaining(row: pd.Series) -> str:
    if str(row.get("Trạng_Thái", "")) == "Đã xong":
        return "Hoàn thành 🎉"
    dl = parse_deadline_timezone(row.get("Deadline", ""))
    if dl is None:
        return "—"
    total_seconds = int((dl - NOW()).total_seconds())
    if total_seconds < 0:
        return "Chạy ngay đi 🛑"
    days, rem  = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0:   return f"{days} ngày {hours} giờ {minutes} phút"
    if hours > 0:  return f"{hours} giờ {minutes} phút"
    return f"{minutes} phút"

def get_user_name(user_id, users_df):
    match = users_df[users_df["User_ID"] == user_id]
    return match.iloc[0]["Tên"] if not match.empty else f"Unknown ({user_id})"

# ═══════════════════════════════════════════════════════════
#  4. AUTH SYSTEM
# ═══════════════════════════════════════════════════════════

def show_auth_page(data):
    users_df = data["users"]
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🛡️ DEADLINE SLAYER</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888;'>Nền tảng quản lý học tập & Giao việc nhóm</p>", unsafe_allow_html=True)

        tab_login, tab_reg = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký Tài Khoản"])

        with tab_login:
            st.subheader("Đăng nhập hệ thống")
            log_id   = st.text_input("User ID (VD: U001)", key="log_id").strip()
            log_pass = st.text_input("Mật khẩu", type="password", key="log_pass")
            if st.button("🚀 Đăng Nhập", use_container_width=True, type="primary"):
                fetch_all_data.clear()
                fresh_data  = fetch_all_data()
                fresh_users = fresh_data["users"]
                if fresh_users.empty:
                    st.error("Hệ thống chưa có tài khoản nào. Vui lòng đăng ký!")
                else:
                    user_match = fresh_users[
                        (fresh_users["User_ID"] == log_id) &
                        (fresh_users["Password"] == log_pass)
                    ]
                    if not user_match.empty:
                        st.session_state['logged_in']    = True
                        st.session_state['current_user'] = user_match.iloc[0].to_dict()
                        st.success("Đăng nhập thành công!")
                        st.rerun()
                    else:
                        st.error("Sai User ID hoặc mật khẩu!")

        with tab_reg:
            st.subheader("Tạo tài khoản mới")
            reg_name  = st.text_input("Họ và Tên",  key="reg_name").strip()
            reg_email = st.text_input("Email",       key="reg_email").strip()
            reg_pass  = st.text_input("Mật khẩu",   type="password", key="reg_pass")
            reg_wh_dm = st.text_input(
                "🤖 Discord Webhook cá nhân (tuỳ chọn):",
                placeholder="https://discord.com/api/webhooks/...",
                help="Bot sẽ gửi tin nhắn riêng (DM) từ bạn bè vào kênh Discord cá nhân của bạn.",
                key="reg_wh_dm"
            ).strip()

            if st.button("Tạo Tài Khoản", use_container_width=True):
                if not reg_name or not reg_email or not reg_pass:
                    st.error("Vui lòng điền đầy đủ thông tin!")
                else:
                    fetch_all_data.clear()
                    fresh_users = fetch_all_data()["users"]
                    if not fresh_users.empty and reg_email in fresh_users["Email"].values:
                        st.error("Email này đã được sử dụng!")
                    else:
                        if fresh_users.empty:
                            new_id = "U001"
                        else:
                            ids  = fresh_users["User_ID"].dropna().astype(str).tolist()
                            nums = [int(i[1:]) for i in ids if i.startswith("U") and i[1:].isdigit()]
                            new_id = f"U{(max(nums) + 1 if nums else 1):03d}"

                        append_row_data(WS_USERS, [
                            new_id, reg_pass, reg_name, reg_email, "",
                            reg_wh_dm,
                            NOW().strftime("%Y-%m-%d %H:%M:%S")
                        ])
                        fetch_all_data.clear()
                        st.success(
                            f"🎉 Tài khoản tạo thành công!\n\n"
                            f"**USER ID CỦA BẠN LÀ: `{new_id}`**\n\n"
                            f"(Dùng ID này để đăng nhập và kết bạn)"
                        )

# ═══════════════════════════════════════════════════════════
#  5. MAIN APP
# ═══════════════════════════════════════════════════════════

def main_app(data):
    users_df  = data["users"]
    groups_df = data["groups"]
    tasks_df  = data["tasks"]
    current_user = st.session_state['current_user']
    my_id = current_user["User_ID"]

    is_leader = not groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id].empty

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("## ⚔️ DEADLINE SLAYER")
        st.markdown("---")
        st.success(f"👤 **{current_user['Tên']}**\n\n🆔 ID: `{my_id}`")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state['logged_in']    = False
            st.session_state['current_user'] = None
            st.rerun()

        st.markdown("---")
        st.subheader("⚙️ Cấu hình")
        s_name = st.text_input("Tên Google Sheets", value=st.session_state["sheet_name"])
        if s_name != st.session_state["sheet_name"]:
            st.session_state["sheet_name"] = s_name
            fetch_all_data.clear()
            st.rerun()

        # Cài đặt Discord Webhook DM cá nhân
        st.markdown("---")
        st.markdown("### 🔔 Discord Webhook Cá Nhân")
        my_row    = users_df[users_df["User_ID"] == my_id]
        cur_wh_dm = str(my_row.iloc[0].get("Discord_Webhook_DM", "")).strip() if not my_row.empty else ""
        new_wh_dm = st.text_input(
            "Webhook nhận DM của bạn:",
            value=cur_wh_dm,
            placeholder="https://discord.com/api/webhooks/...",
            help="Tin nhắn riêng gửi đến bạn sẽ được đẩy về đây.",
            key="sidebar_wh_dm"
        ).strip()
        if st.button("💾 Lưu Webhook DM", use_container_width=True):
            update_cell_by_id(WS_USERS, "User_ID", my_id, "Discord_Webhook_DM", new_wh_dm, USER_COLS)
            fetch_all_data.clear()
            st.toast("Đã lưu Webhook DM!")

        if is_leader:
            st.markdown("---")
            st.markdown("### 🤖 Bảng Điều Khiển Bot Nhóm")
            my_groups = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
            grp_opts  = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in my_groups.iterrows()}
            sel_grp   = st.selectbox("Chọn nhóm:", options=list(grp_opts.keys()), format_func=lambda x: grp_opts[x])
            msg_text  = st.text_area("Tin nhắn thông báo:")
            admin_file = st.file_uploader("Đính kèm file (Tuỳ chọn)")
            if st.button("🚀 Bắn Lệnh Lên Discord", use_container_width=True, type="primary"):
                wh  = get_group_webhook(sel_grp, groups_df)
                msg = f"📢 **[THÔNG BÁO TỪ TRƯỞNG NHÓM {current_user['Tên']}]**\n{msg_text}"
                if admin_file:
                    success = push_to_discord(msg, webhook_url=wh, file_bytes=admin_file.getvalue(), filename=admin_file.name)
                else:
                    success = push_to_discord(msg, webhook_url=wh)
                st.toast("Đã bắn thông báo!" if success else "Gửi thất bại. Kiểm tra lại Webhook.")

        st.markdown("---")
        if st.button("🔄 Cập nhật dữ liệu", use_container_width=True):
            fetch_all_data.clear()
            st.rerun()

    # --- TABS ---
    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📊 Dashboard Công Việc",
        "👥 Kết Bạn & Tạo Nhóm",
        "📋 Giao Việc Mới",
        "💬 Chat",
        "🏆 Xếp Hạng",
        "🗑️ Quản Lý Tài Khoản",
    ])

    me_in_db        = users_df[users_df["User_ID"] == my_id].iloc[0]
    my_friends_list = [f.strip() for f in str(me_in_db["Bạn_Bè"]).split(",") if f.strip()]

    with t1: render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader)
    with t2: render_network(users_df, groups_df, my_id, my_friends_list)
    with t3: render_assign_task(users_df, groups_df, tasks_df, my_id, my_friends_list)
    with t4: render_chat(data["chat"], data["dm"], groups_df, users_df, my_id, my_friends_list)
    with t5: render_leaderboard(tasks_df, users_df)
    with t6: render_account_management(users_df, my_id)


# ═══════════════════════════════════════════════════════════
#  6. TAB 1: DASHBOARD
# ═══════════════════════════════════════════════════════════

def render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader):
    st.subheader("Bảng Tiến Độ Cá Nhân & Nhóm")

    my_groups    = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
    subordinates = []
    for _, grp in my_groups.iterrows():
        subordinates.extend([m.strip() for m in str(grp["Thành_Viên_IDs"]).split(",") if m.strip()])

    visible_tasks = tasks_df[
        (tasks_df["Người_Phụ_Trách_ID"] == my_id) |
        (tasks_df["Người_Phụ_Trách_ID"].isin(subordinates))
    ].copy()

    if visible_tasks.empty:
        st.info("Chưa có công việc nào dành cho bạn hoặc nhóm của bạn.")
        return

    visible_tasks["Tiến_Độ_%"]  = visible_tasks["Tiến_Độ_%"].apply(clean_and_parse_progress)
    visible_tasks["_status"]     = visible_tasks.apply(calculate_task_status, axis=1)
    visible_tasks["_remaining"]  = visible_tasks.apply(format_time_remaining, axis=1)

    for _, row in visible_tasks.iterrows():
        b_color = {
            "done": "#2e7d32", "overdue": "#d32f2f",
            "urgent": "#f57c00", "warning": "#fbc02d", "safe": "#1976d2"
        }.get(row["_status"], "#cccccc")
        assignee_name = get_user_name(row['Người_Phụ_Trách_ID'], users_df)

        st.markdown(f"""
        <div style="border:1px solid {b_color}; border-left:5px solid {b_color}; background:#111112;
             border-radius:10px; padding:12px 16px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between;">
                <b>📌 {row['Tên_Công_Việc']}</b>
                <span style="color:{b_color}; font-weight:bold;">{row['_status'].upper()}</span>
            </div>
            <div style="font-size:13px; color:#aaa; margin-top:5px;">
                👤 Phụ trách: <b>{assignee_name}</b> | ⏰ Hạn: {row['Deadline']}
            </div>
            <div style="font-size:14px; color:{b_color}; font-weight:500; margin-top:3px;">
                ⏳ Đếm ngược: {row['_remaining']} | Tiến độ: {row['Tiến_Độ_%']}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        if row['Người_Phụ_Trách_ID'] == my_id:
            with st.expander("Tương tác & Cập nhật & Nộp Minh Chứng"):
                c1, c2 = st.columns(2)
                with c1:
                    np_ = st.slider("Cập nhật %", 0, 100, int(row["Tiến_Độ_%"]), key=f"sld_{row['ID']}")
                    if st.button("💾 Lưu Tiến Độ", key=f"btn_{row['ID']}"):
                        update_cell_by_id(WS_TASKS, "ID", row["ID"], "Tiến_Độ_%", np_, TASK_COLS)
                        if np_ == 100:
                            update_cell_by_id(WS_TASKS, "ID", row["ID"], "Trạng_Thái", "Đã xong", TASK_COLS)
                        st.rerun()
                with c2:
                    st.markdown("**Nộp file minh chứng / Tài liệu đồ án**")
                    proof_file = st.file_uploader("Gửi thẳng lên Discord nhóm", key=f"file_{row['ID']}")
                    if st.button("📤 Nộp lên Discord", key=f"proof_btn_{row['ID']}"):
                        if proof_file:
                            assignee_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False)]
                            sent_count = 0
                            for _, grp in assignee_groups.iterrows():
                                wh = str(grp.get("Discord_Webhook", "")).strip()
                                if wh:
                                    msg = f"✅ **{assignee_name}** đã nộp minh chứng cho task: **{row['Tên_Công_Việc']}**"
                                    if push_to_discord(msg, webhook_url=wh, file_bytes=proof_file.getvalue(), filename=proof_file.name):
                                        sent_count += 1
                            if sent_count > 0:
                                st.success("Đã đẩy file minh chứng lên Discord nhóm!")
                            else:
                                st.warning("Thất bại. Nhóm chưa cài Discord Webhook.")
                        else:
                            st.error("Bạn chưa đính kèm file nào!")

# ═══════════════════════════════════════════════════════════
#  7. TAB 2: KẾT BẠN & TẠO NHÓM
# ═══════════════════════════════════════════════════════════

def render_network(users_df, groups_df, my_id, my_friends_list):
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("🔍 Tìm & Kết Bạn")
        search_id = st.text_input("Nhập User ID để tìm kiếm (VD: U001):").strip()
        if st.button("Kết bạn"):
            if search_id == my_id:
                st.warning("Bạn không thể tự kết bạn với chính mình!")
            elif search_id in my_friends_list:
                st.info("Người này đã là bạn bè của bạn rồi.")
            else:
                target_user = users_df[users_df["User_ID"] == search_id]
                if target_user.empty:
                    st.error("Không tìm thấy người dùng mang ID này!")
                else:
                    new_friends = my_friends_list + [search_id]
                    update_cell_by_id(WS_USERS, "User_ID", my_id, "Bạn_Bè", ",".join(new_friends), USER_COLS)
                    st.success(f"Đã thêm {target_user.iloc[0]['Tên']} vào danh sách bạn bè!")
                    st.rerun()

        st.markdown("---")
        st.markdown("**Danh sách bạn bè của bạn:**")
        if not my_friends_list:
            st.caption("Bạn chưa có người bạn nào.")
        for f_id in my_friends_list:
            st.markdown(f"- {get_user_name(f_id, users_df)} (`{f_id}`)")

    with c2:
        st.subheader("🏢 Tạo Nhóm Học Tập Mới")
        st.markdown("Người tạo nhóm sẽ tự động trở thành Trưởng Nhóm.")
        grp_name    = st.text_input("Tên nhóm học tập:")
        grp_webhook = st.text_input(
            "🤖 Discord Webhook URL của nhóm (tuỳ chọn):",
            placeholder="https://discord.com/api/webhooks/...",
            help="Bot sẽ gửi thông báo vào kênh Discord của nhóm này."
        ).strip()

        friend_options   = {f_id: f"{get_user_name(f_id, users_df)} ({f_id})" for f_id in my_friends_list}
        selected_friends = st.multiselect(
            "Chọn bạn bè thêm vào nhóm:",
            options=list(friend_options.keys()),
            format_func=lambda x: friend_options[x]
        )

        if st.button("Tạo Nhóm", type="primary"):
            if not grp_name:
                st.error("Vui lòng nhập tên nhóm!")
            elif not selected_friends:
                st.error("Nhóm phải có ít nhất 1 thành viên ngoài bạn!")
            else:
                if groups_df.empty:
                    new_gid = "G001"
                else:
                    ids  = groups_df["Group_ID"].dropna().astype(str).tolist()
                    nums = [int(i[1:]) for i in ids if i.startswith("G") and i[1:].isdigit()]
                    new_gid = f"G{(max(nums) + 1 if nums else 1):03d}"

                all_members = [my_id] + selected_friends
                append_row_data(WS_GROUPS, [
                    new_gid, grp_name, my_id, ",".join(all_members),
                    grp_webhook, NOW().strftime("%Y-%m-%d")
                ])
                if grp_webhook:
                    push_to_discord(
                        f"🎉 Nhóm **{grp_name}** đã được tạo!",
                        webhook_url=grp_webhook
                    )
                st.success(f"Đã tạo nhóm {grp_name} thành công!")
                st.rerun()

        st.markdown("---")
        st.markdown("**Các nhóm bạn tham gia:**")
        my_joined_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False)]
        if my_joined_groups.empty:
            st.caption("Chưa tham gia nhóm nào.")
        for _, g in my_joined_groups.iterrows():
            role    = "👑 Trưởng nhóm" if g["Trưởng_Nhóm_ID"] == my_id else "👤 Thành viên"
            has_bot = "🤖" if str(g.get("Discord_Webhook", "")).strip() else "🔕"
            st.markdown(f"- **{g['Tên_Nhóm']}** ({role}) {has_bot}")

    # --- QUẢN LÝ NHÓM DÀNH CHO TRƯỞNG NHÓM ---
    st.markdown("---")
    st.subheader("⚙️ Quản Lý Nhóm (Dành cho Trưởng Nhóm)")
    my_led_groups = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]

    if my_led_groups.empty:
        st.info("Bạn chưa làm trưởng nhóm nào. Hãy tạo nhóm mới để trải nghiệm tính năng này.")
    else:
        edit_grp_id = st.selectbox(
            "Chọn nhóm để chỉnh sửa/xóa:",
            options=my_led_groups["Group_ID"].tolist(),
            format_func=lambda x: my_led_groups[my_led_groups["Group_ID"] == x]["Tên_Nhóm"].iloc[0]
        )
        grp_data = my_led_groups[my_led_groups["Group_ID"] == edit_grp_id].iloc[0]

        with st.expander(f"🛠 Chỉnh sửa: {grp_data['Tên_Nhóm']}", expanded=True):
            new_grp_name = st.text_input("Đổi tên nhóm:", value=grp_data["Tên_Nhóm"], key=f"name_{edit_grp_id}")
            new_webhook  = st.text_input("Đổi Discord Webhook:", value=grp_data.get("Discord_Webhook", ""), key=f"wh_{edit_grp_id}")

            current_members     = [m.strip() for m in str(grp_data["Thành_Viên_IDs"]).split(",") if m.strip() and m.strip() != my_id]
            valid_cur_members   = [m for m in current_members if m in friend_options]
            new_members         = st.multiselect(
                "Thêm/Bớt thành viên (từ danh sách bạn bè):",
                options=list(friend_options.keys()),
                default=valid_cur_members,
                format_func=lambda x: friend_options[x],
                key=f"mem_{edit_grp_id}"
            )

            col_save, col_del = st.columns(2)
            with col_save:
                if st.button("💾 Lưu Thay Đổi Nhóm", type="primary", use_container_width=True):
                    final_members = [my_id] + new_members
                    update_cell_by_id(WS_GROUPS, "Group_ID", edit_grp_id, "Tên_Nhóm", new_grp_name, GROUP_COLS)
                    update_cell_by_id(WS_GROUPS, "Group_ID", edit_grp_id, "Thành_Viên_IDs", ",".join(final_members), GROUP_COLS)
                    update_cell_by_id(WS_GROUPS, "Group_ID", edit_grp_id, "Discord_Webhook", new_webhook, GROUP_COLS)
                    st.success("Đã cập nhật thông tin nhóm!")
                    st.rerun()
            with col_del:
                if st.button("🗑️ Xóa Nhóm Này", use_container_width=True):
                    delete_row_by_id(WS_GROUPS, "Group_ID", edit_grp_id, GROUP_COLS)
                    st.success("Đã xóa nhóm thành công!")
                    st.rerun()

# ═══════════════════════════════════════════════════════════
#  8. TAB 3: GIAO VIỆC
# ═══════════════════════════════════════════════════════════

def render_assign_task(users_df, groups_df, tasks_df, my_id, my_friends_list):
    st.subheader("📋 Giao Việc (Chỉ giao được cho Bạn Bè hoặc Bản thân)")

    assignee_options = {my_id: f"Tự làm ({get_user_name(my_id, users_df)})"}
    for f_id in my_friends_list:
        assignee_options[f_id] = f"{get_user_name(f_id, users_df)} (Bạn bè)"

    with st.form("assign_form"):
        t_name      = st.text_input("Tên Nhiệm Vụ *")
        subj        = st.text_input("Thuộc môn học")
        assignee_id = st.selectbox(
            "Chọn người làm *",
            options=list(assignee_options.keys()),
            format_func=lambda x: assignee_options[x]
        )
        col1, col2 = st.columns(2)
        with col1: d_date = st.date_input("Ngày chốt", min_value=NOW().date())
        with col2: d_time = st.time_input("Giờ chốt")
        pri   = st.selectbox("Độ quan trọng", ["Cao", "Trung bình", "Thấp"])
        notes = st.text_area("Ghi chú")

        if st.form_submit_button("Phát Lệnh 🚀"):
            if not t_name:
                st.error("Không được để trống tên!")
            else:
                new_id  = f"T{len(tasks_df)+1:03d}" if not tasks_df.empty else "T001"
                full_dl = f"{d_date} {d_time.strftime('%H:%M:%S')}"
                append_row_data(WS_TASKS, [
                    new_id, t_name, subj, assignee_id, full_dl, pri,
                    "Chưa xong", 0, "Bắt đầu", notes, 5, "",
                    NOW().strftime("%Y-%m-%d %H:%M:%S"), ""
                ])
                assignee_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(assignee_id, na=False)]
                notified = set()
                for _, grp in assignee_groups.iterrows():
                    wh = str(grp.get("Discord_Webhook", "")).strip()
                    if wh and wh not in notified:
                        push_to_discord(
                            f"🚨 Giao việc mới: **{t_name}** → {get_user_name(assignee_id, users_df)}!\n"
                            f"📅 Hạn: {full_dl} | 🔥 Ưu tiên: {pri}",
                            webhook_url=wh
                        )
                        notified.add(wh)
                st.success("Giao việc thành công!")
                st.rerun()

# ═══════════════════════════════════════════════════════════
#  9. TAB 4: CHAT (NHÓM + CÁ NHÂN)
# ═══════════════════════════════════════════════════════════

def render_chat(chat_df, dm_df, groups_df, users_df, my_id, my_friends_list):
    """
    Tab Chat với 2 sub-tab:
      • Chat Nhóm  – lưu vào sheet ChatRoom, đẩy Discord Webhook nhóm
      • Tin Nhắn Riêng (DM) – lưu vào sheet DirectMessages, đẩy Discord Webhook cá nhân người nhận
    """
    st.subheader("💬 Chat")

    sub_group, sub_dm = st.tabs(["🏢 Chat Nhóm", "🔒 Tin Nhắn Riêng (DM)"])

    # ── 9a. CHAT NHÓM ───────────────────────────────────────
    with sub_group:
        my_joined_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False)]

        if my_joined_groups.empty:
            st.warning("Bạn chưa có nhóm nào để chat. Hãy tạo nhóm ở tab 'Kết Bạn & Tạo Nhóm' nhé.")
        else:
            group_options = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in my_joined_groups.iterrows()}
            selected_gid  = st.selectbox(
                "Chọn nhóm:",
                options=list(group_options.keys()),
                format_func=lambda x: group_options[x],
                key="chat_grp_select"
            )

            # Hiển thị tin nhắn nhóm
            st.markdown("---")
            chat_container = st.container(height=350)
            with chat_container:
                group_chats = chat_df[chat_df["Group_Nhận_ID"] == selected_gid]
                if group_chats.empty:
                    st.caption("Chưa có tin nhắn nào trong nhóm này.")
                for _, row in group_chats.iterrows():
                    sender_name = get_user_name(row["Người_Gửi_ID"], users_df)
                    is_me       = row["Người_Gửi_ID"] == my_id
                    css_class   = "chat-me" if is_me else "chat-card"
                    label_color = "#4CAF50" if is_me else "#5865F2"
                    st.markdown(f"""
                    <div class="{css_class}">
                        <small style='color:{label_color};'><b>{sender_name}</b> • {row['Thời_Gian']}</small><br>
                        <span>{row['Nội_Dung']}</span>
                    </div>""", unsafe_allow_html=True)

            # Form gửi tin nhắn nhóm
            with st.form("chat_grp_form", clear_on_submit=True):
                msg_grp     = st.text_input("Nhập tin nhắn...", key="grp_msg_input")
                upload_grp  = st.file_uploader(
                    "📎 Đính kèm tài liệu (Gửi lên Discord nhóm)",
                    help="Discord Webhook hỗ trợ file tối đa 8MB–25MB.",
                    key="grp_file_input"
                )
                if st.form_submit_button("📨 Gửi vào Nhóm"):
                    if msg_grp.strip() or upload_grp:
                        sheet_msg = msg_grp.strip()
                        if upload_grp:
                            sheet_msg += f" [📎 {upload_grp.name}]"
                        if sheet_msg:
                            append_row_data(WS_CHAT, [
                                NOW().strftime("%Y-%m-%d %H:%M:%S"),
                                my_id, selected_gid, sheet_msg
                            ])

                        wh = get_group_webhook(selected_gid, groups_df)
                        if wh:
                            sender      = get_user_name(my_id, users_df)
                            group_label = group_options[selected_gid]
                            discord_msg = (
                                f"💬 **{sender}** › [{group_label}]:\n{msg_grp.strip()}"
                                if msg_grp.strip()
                                else f"📎 **{sender}** vừa gửi tệp đính kèm vào nhóm **{group_label}**."
                            )
                            if upload_grp:
                                push_to_discord(discord_msg, webhook_url=wh,
                                                file_bytes=upload_grp.getvalue(), filename=upload_grp.name)
                            else:
                                push_to_discord(discord_msg, webhook_url=wh)
                        st.rerun()
                    else:
                        st.warning("Vui lòng nhập tin nhắn hoặc đính kèm file.")

    # ── 9b. TIN NHẮN RIÊNG (DM) ─────────────────────────────
    with sub_dm:
        if not my_friends_list:
            st.warning("Bạn chưa có bạn bè nào. Hãy kết bạn ở tab 'Kết Bạn & Tạo Nhóm' để nhắn tin riêng.")
        else:
            friend_opts = {f_id: f"{get_user_name(f_id, users_df)} ({f_id})" for f_id in my_friends_list}
            selected_friend = st.selectbox(
                "Chọn người để nhắn tin riêng:",
                options=list(friend_opts.keys()),
                format_func=lambda x: friend_opts[x],
                key="dm_friend_select"
            )

            # Kiểm tra webhook của người nhận
            receiver_wh = get_user_dm_webhook(selected_friend, users_df)
            if receiver_wh:
                st.caption(f"🤖 Người nhận đã cài Discord Webhook cá nhân — tin nhắn sẽ tự động đẩy lên Discord của họ.")
            else:
                st.caption(f"🔕 Người nhận chưa cài Discord Webhook cá nhân — tin nhắn chỉ hiển thị trên web.")

            st.markdown("---")

            # Lọc tin nhắn DM giữa 2 người (2 chiều)
            dm_container = st.container(height=350)
            with dm_container:
                if dm_df.empty:
                    st.caption("Chưa có tin nhắn nào.")
                else:
                    convo = dm_df[
                        ((dm_df["Người_Gửi_ID"] == my_id)      & (dm_df["Người_Nhận_ID"] == selected_friend)) |
                        ((dm_df["Người_Gửi_ID"] == selected_friend) & (dm_df["Người_Nhận_ID"] == my_id))
                    ].copy()

                    if convo.empty:
                        st.caption(f"Chưa có tin nhắn riêng nào với {get_user_name(selected_friend, users_df)}.")
                    for _, row in convo.iterrows():
                        sender_name = get_user_name(row["Người_Gửi_ID"], users_df)
                        is_me       = row["Người_Gửi_ID"] == my_id
                        css_class   = "chat-me" if is_me else "chat-private"
                        label_color = "#4CAF50" if is_me else "#7289DA"
                        st.markdown(f"""
                        <div class="{css_class}">
                            <small style='color:{label_color};'><b>{sender_name}</b> • {row['Thời_Gian']}</small><br>
                            <span>{row['Nội_Dung']}</span>
                        </div>""", unsafe_allow_html=True)

            # Form gửi DM
            with st.form("chat_dm_form", clear_on_submit=True):
                msg_dm    = st.text_input("Nhập tin nhắn riêng...", key="dm_msg_input")
                upload_dm = st.file_uploader(
                    "📎 Đính kèm file (Gửi lên Discord cá nhân người nhận)",
                    help="Cần người nhận đã cài Discord Webhook DM cá nhân.",
                    key="dm_file_input"
                )
                if st.form_submit_button("🔒 Gửi Tin Nhắn Riêng"):
                    if msg_dm.strip() or upload_dm:
                        sheet_msg = msg_dm.strip()
                        if upload_dm:
                            sheet_msg += f" [📎 {upload_dm.name}]"
                        if sheet_msg:
                            append_row_data(WS_DM, [
                                NOW().strftime("%Y-%m-%d %H:%M:%S"),
                                my_id, selected_friend, sheet_msg
                            ])

                        # Đẩy lên Discord Webhook DM của NGƯỜI NHẬN
                        if receiver_wh:
                            sender_name = get_user_name(my_id, users_df)
                            discord_msg = (
                                f"📩 **Tin nhắn riêng từ {sender_name}:**\n{msg_dm.strip()}"
                                if msg_dm.strip()
                                else f"📎 **{sender_name}** vừa gửi cho bạn một tệp đính kèm."
                            )
                            if upload_dm:
                                push_to_discord(discord_msg, webhook_url=receiver_wh,
                                                file_bytes=upload_dm.getvalue(), filename=upload_dm.name)
                            else:
                                push_to_discord(discord_msg, webhook_url=receiver_wh)

                        st.rerun()
                    else:
                        st.warning("Vui lòng nhập tin nhắn hoặc đính kèm file.")

# ═══════════════════════════════════════════════════════════
#  10. TAB 5: LEADERBOARD
# ═══════════════════════════════════════════════════════════

def render_leaderboard(tasks_df, users_df):
    st.subheader("🏆 Bảng Xếp Hạng")
    if tasks_df.empty:
        st.info("Chưa có data.")
        return

    tasks = tasks_df.copy()
    tasks["Tiến_Độ_%"] = tasks["Tiến_Độ_%"].apply(clean_and_parse_progress)
    tasks["_status"]   = tasks.apply(calculate_task_status, axis=1)

    grouped = tasks.groupby("Người_Phụ_Trách_ID").apply(lambda g: pd.Series({
        "Tổng Task": len(g),
        "Đã Xong":   (g["_status"] == "done").sum(),
        "Tiến độ TB": f"{int(g['Tiến_Độ_%'].mean())}%",
    })).reset_index()

    grouped["Tên Thành Viên"] = grouped["Người_Phụ_Trách_ID"].apply(lambda x: get_user_name(x, users_df))
    grouped = grouped[["Tên Thành Viên", "Tổng Task", "Đã Xong", "Tiến độ TB"]]
    st.dataframe(grouped.sort_values(by="Đã Xong", ascending=False), use_container_width=True)

# ═══════════════════════════════════════════════════════════
#  11. TAB 6: QUẢN LÝ TÀI KHOẢN
# ═══════════════════════════════════════════════════════════

def render_account_management(users_df, my_id):
    st.subheader("🗑️ Quản Lý Tài Khoản")
    st.markdown("### Danh sách tất cả tài khoản trong hệ thống")
    if users_df.empty:
        st.info("Không có tài khoản nào.")
        return

    display_cols = ["User_ID", "Tên", "Email", "Ngày_Tạo"]
    st.dataframe(users_df[display_cols], use_container_width=True)

    st.markdown("---")
    st.markdown("### 🗑️ Xóa Tài Khoản")
    st.warning("⚠️ Bạn không thể xóa tài khoản của chính mình ở đây.")

    other_users = users_df[users_df["User_ID"] != my_id]
    if other_users.empty:
        st.info("Không có tài khoản nào khác để xóa.")
        return

    user_opts = {
        row["User_ID"]: f"{row['Tên']} ({row['User_ID']}) — {row['Email']}"
        for _, row in other_users.iterrows()
    }
    del_id  = st.selectbox("Chọn tài khoản cần xóa:", options=list(user_opts.keys()), format_func=lambda x: user_opts[x])
    confirm = st.checkbox(f"Tôi xác nhận muốn xóa tài khoản `{del_id}`")
    if st.button("🗑️ Xóa Tài Khoản", type="primary", disabled=not confirm):
        ok = delete_row_by_id(WS_USERS, "User_ID", del_id, USER_COLS)
        if ok:
            st.success(f"Đã xóa tài khoản `{del_id}` thành công!")
            fetch_all_data.clear()
            st.rerun()
        else:
            st.error("Không tìm thấy hoặc không thể xóa tài khoản này.")

# ═══════════════════════════════════════════════════════════
#  MAIN EXECUTION
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    data = fetch_all_data()
    if not st.session_state['logged_in']:
        show_auth_page(data)
    else:
        main_app(data)