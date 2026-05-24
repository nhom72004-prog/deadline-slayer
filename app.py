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

# ═══════════════════════════════════════════════════════════
#  0. INIT & CONFIG
# ═══════════════════════════════════════════════════════════
if not os.path.exists("credentials.json"):
    if "gcp_service_account" in st.secrets:
        with open("credentials.json", "w") as f:
            json.dump(dict(st.secrets["gcp_service_account"]), f)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
def NOW():
    return datetime.now(TZ)

st.set_page_config(page_title="Deadline Slayer ⚔️", page_icon="⚔️", layout="wide", initial_sidebar_state="expanded")

for k, v in [("sheet_name","DeadlineSlayer_DB"),("logged_in",False),("current_user",None)]:
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif;}
[data-testid="metric-container"]{
    background:#16161a;border:1px solid rgba(255,255,255,0.08);
    border-radius:12px;padding:16px !important;box-shadow:0 4px 6px rgba(0,0,0,.2);}
.stButton>button[kind="primary"]{background:#5865F2;border:none;border-radius:8px;font-weight:700;color:white;}
.stButton>button[kind="primary"]:hover{background:#404EED;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  1. SCHEMA
# ═══════════════════════════════════════════════════════════
SCOPES = ["https://spreadsheets.google.com/feeds",
          "https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

WS_TASKS="Tasks"; WS_USERS="Users"; WS_GROUPS="Groups"
WS_PROOFS="Proofs"; WS_CHAT="ChatRoom"; WS_DM="DirectMessages"

TASK_COLS  = ["ID","Tên_Công_Việc","Môn_Học","Người_Phụ_Trách_ID","Deadline",
              "Độ_Ưu_Tiên","Trạng_Thái","Tiến_Độ_%","Giai_Đoạn_Hiện_Tại",
              "Ghi_Chú","Nhắc_Mỗi_Phút","Nhắc_Lần_Cuối","Ngày_Tạo","Ngày_Cập_Nhật"]
USER_COLS  = ["User_ID","Password","Tên","Email","Bạn_Bè","Discord_Webhook_DM","Ngày_Tạo"]
GROUP_COLS = ["Group_ID","Tên_Nhóm","Trưởng_Nhóm_ID","Thành_Viên_IDs","Discord_Webhook","Ngày_Tạo"]
PROOF_COLS = ["Task_ID","Người_Nộp_ID","Thời_Gian","Mô_Tả","Giai_Đoạn","URL_File"]
CHAT_COLS  = ["Thời_Gian","Người_Gửi_ID","Group_Nhận_ID","Nội_Dung","Loại","File_Tên","File_URL"]
DM_COLS    = ["Thời_Gian","Người_Gửi_ID","Người_Nhận_ID","Nội_Dung","Loại","File_Tên","File_URL"]

# ═══════════════════════════════════════════════════════════
#  2. MESSAGES & HELPERS
# ═══════════════════════════════════════════════════════════
def clean_progress(val):
    if pd.isna(val) or val == "": return 0.0
    try: return float(str(val).replace("%", "").strip())
    except: return 0.0

def parse_dl(dl_str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M"):
        try: return datetime.strptime(str(dl_str).strip(), fmt).replace(tzinfo=TZ)
        except: continue
    return None

def calc_status(row):
    if str(row.get("Trạng_Thái", "")) == "Đã xong" or clean_progress(row.get("Tiến_Độ_%")) == 100:
        return "done"
    dl = parse_dl(row.get("Deadline", ""))
    if dl is None: return "unknown"
    h = (dl - NOW()).total_seconds() / 3600
    if h < 0:   return "overdue"
    if h <= 24: return "urgent"
    if h <= 72: return "warning"
    return "safe"

def fmt_remaining(row):
    if str(row.get("Trạng_Thái", "")) == "Đã xong": return "Xong sạch rồi 🎉"
    dl = parse_dl(row.get("Deadline", ""))
    if dl is None: return "—"
    s = int((dl - NOW()).total_seconds())
    if s < 0: return "ĐÃ QUÁ HẠN! 🛑"
    d, r = divmod(s, 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60)
    if d > 3:  return f"⏳ Còn {d}n {h}g"
    if d > 0:  return f"⚡ Còn {d}n {h}g {m}p"
    if h > 3:  return f"🔥 Còn {h}g {m}p"
    if h > 0:  return f"🚨 Còn {h}g {m}p — KHẨN!"
    return f"💀 Còn {m}p!!! FULL SEND!!!"

def get_user_name(uid, users_df):
    m = users_df[users_df["User_ID"] == uid]
    return m.iloc[0]["Tên"] if not m.empty else f"Ẩn danh ({uid})"

def push_to_discord(message, webhook_url="", file_bytes=None, filename=None):
    if not webhook_url or "discord.com/api/webhooks" not in webhook_url: return False
    try:
        if file_bytes and filename:
            r = requests.post(webhook_url, data={"content": message}, files={"file": (filename, file_bytes)}, timeout=15)
        else:
            r = requests.post(webhook_url, json={"content": message}, timeout=5)
        return r.status_code in (200, 204)
    except: return False

# ═══════════════════════════════════════════════════════════
#  3. GOOGLE SHEETS
# ═══════════════════════════════════════════════════════════
@st.cache_resource(ttl=15)
def get_sheets_client():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPES)
        return gspread.authorize(creds)
    except: return None

def init_spreadsheet_structure(ss):
    existing = {ws.title: ws for ws in ss.worksheets()}
    schema = {WS_TASKS: TASK_COLS, WS_USERS: USER_COLS, WS_GROUPS: GROUP_COLS, 
              WS_PROOFS: PROOF_COLS, WS_CHAT: CHAT_COLS, WS_DM: DM_COLS}
    for name, cols in schema.items():
        if name not in existing:
            ws = ss.add_worksheet(title=name, rows=1000, cols=max(len(cols), 10))
            ws.append_row(cols)

@st.cache_data(ttl=1)
def fetch_all_data():
    client = get_sheets_client()
    empty = {k: pd.DataFrame(columns=c) for k, c in [("tasks", TASK_COLS), ("users", USER_COLS), 
            ("groups", GROUP_COLS), ("proofs", PROOF_COLS), ("chat", CHAT_COLS), ("dm", DM_COLS)]}
    if not client: return empty
    try:
        ss = client.open(st.session_state["sheet_name"])
        init_spreadsheet_structure(ss)
        def get_df(name, cols):
            vals = ss.worksheet(name).get_all_values()
            if not vals or len(vals) <= 1: return pd.DataFrame(columns=cols)
            df = pd.DataFrame(vals[1:], columns=vals[0])
            for col in cols:
                if col not in df.columns: df[col] = ""
            return df[cols].fillna("")
        return {k: get_df(n, c) for k, n, c in [("tasks", WS_TASKS, TASK_COLS), ("users", WS_USERS, USER_COLS),
                ("groups", WS_GROUPS, GROUP_COLS), ("proofs", WS_PROOFS, PROOF_COLS), 
                ("chat", WS_CHAT, CHAT_COLS), ("dm", WS_DM, DM_COLS)]}
    except: return empty

def append_row_data(name, row):
    ws = get_sheets_client().open(st.session_state["sheet_name"]).worksheet(name)
    try:
        ws.append_row(list(row), value_input_option="USER_ENTERED")
        fetch_all_data.clear()
        return True
    except: return False

def update_cell_by_id(ws_name, id_col, item_id, upd_col, new_val, schema):
    ws = get_sheets_client().open(st.session_state["sheet_name"]).worksheet(ws_name)
    try:
        actual_header = ws.row_values(1)
        id_col_idx = actual_header.index(id_col) + 1
        upd_col_idx = actual_header.index(upd_col) + 1
        cell = ws.find(str(item_id))
        if cell and cell.col == id_col_idx:
            ws.update_cell(cell.row, upd_col_idx, new_val)
            fetch_all_data.clear()
    except: pass

# ═══════════════════════════════════════════════════════════
#  4. AUTH PAGE
# ═══════════════════════════════════════════════════════════
def show_auth_page(data):
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align:center'>🛡️ DEADLINE SLAYER</h1>", unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký"])
        
        with t1:
            log_id   = st.text_input("User ID (VD: U001)", key="log_id").strip()
            log_pass = st.text_input("Mật khẩu", type="password", key="log_pass")
            if st.button("🚀 Đăng Nhập", use_container_width=True, type="primary"):
                fu = data["users"]
                m = fu[(fu["User_ID"] == log_id) & (fu["Password"] == log_pass)]
                if not m.empty:
                    st.session_state.update({"logged_in": True, "current_user": m.iloc[0].to_dict()})
                    st.rerun()
                else:
                    st.error("❌ Sai ID hoặc mật khẩu!")
                    
        with t2:
            rn = st.text_input("Họ và Tên", key="rn").strip()
            re = st.text_input("Email", key="re").strip()
            rp = st.text_input("Mật khẩu", type="password", key="rp")
            if st.button("✨ Tạo Tài Khoản", use_container_width=True):
                if not rn or not re or not rp: st.error("🙏 Điền đủ thông tin!")
                else:
                    fu = data["users"]
                    nums = [int(i[1:]) for i in fu["User_ID"].tolist() if i.startswith("U") and i[1:].isdigit()] if not fu.empty else []
                    new_id = f"U{(max(nums) + 1 if nums else 1):03d}"
                    append_row_data(WS_USERS, [new_id, rp, rn, re, "", "", NOW().strftime("%Y-%m-%d %H:%M:%S")])
                    st.success(f"🎉 Đăng ký thành công! ID của bạn là: {new_id}")

# ═══════════════════════════════════════════════════════════
#  5. RENDER TABS (DASHBOARD & NHÓM)
# ═══════════════════════════════════════════════════════════
def render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader):
    st.subheader("📊 Bảng Tiến Độ Tổng Hợp")
    
    # Lấy các task liên quan: Task được giao + Task giao cho nhóm
    my_groups = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
    subs = []
    for _, g in my_groups.iterrows():
        subs.extend([m.strip() for m in str(g["Thành_Viên_IDs"]).split(",") if m.strip()])
    
    vt = tasks_df[(tasks_df["Người_Phụ_Trách_ID"] == my_id) | (tasks_df["Người_Phụ_Trách_ID"].isin(subs))].copy()
    
    if vt.empty:
        st.info("🎉 Chưa có nhiệm vụ nào!")
        return
        
    vt["Tiến_Độ_%"] = vt["Tiến_Độ_%"].apply(clean_progress)
    vt["_st"]  = vt.apply(calc_status, axis=1)
    vt["_rem"] = vt.apply(fmt_remaining, axis=1)
    
    for _, row in vt.iterrows():
        bc = {"done":"#2e7d32","overdue":"#d32f2f","urgent":"#f57c00","warning":"#fbc02d","safe":"#1976d2"}.get(row["_st"], "#ccc")
        an = get_user_name(row["Người_Phụ_Trách_ID"], users_df)
        st.markdown(f"""
        <div style="border:1px solid {bc};border-left:5px solid {bc}; background:#111112;border-radius:10px;padding:12px;margin-bottom:8px;">
            <b>📌 {row['Tên_Công_Việc']}</b> (Giao cho: {an}) <br>
            <span style="font-size:13px;color:#aaa;">⏰ {row['Deadline']} | {row['_rem']} | Tiến độ: {row['Tiến_Độ_%']}%</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Chỉ người được giao mới được update tiến độ
        if row["Người_Phụ_Trách_ID"] == my_id:
            with st.expander(f"🛠 Cập nhật tiến độ - {row['Tên_Công_Việc']}"):
                np_ = st.slider("Tiến độ %", 0, 100, int(row["Tiến_Độ_%"]), key=f"sld_{row['ID']}")
                if st.button("💾 Lưu", key=f"btn_{row['ID']}"):
                    update_cell_by_id(WS_TASKS, "ID", row["ID"], "Tiến_Độ_%", np_, TASK_COLS)
                    if np_ == 100:
                        update_cell_by_id(WS_TASKS, "ID", row["ID"], "Trạng_Thái", "Đã xong", TASK_COLS)
                    st.rerun()

def render_network_and_tasks(users_df, groups_df, tasks_df, my_id):
    sub1, sub2 = st.tabs(["🏢 Quản Lý Nhóm", "📋 Giao Việc & Danh Sách"])

    with sub1:
        st.subheader("🏢 Tạo Nhóm Mới")
        gn = st.text_input("Tên Nhóm", key="new_group_name")
        if st.button("Tạo Nhóm", type="primary"):
            nums = [int(i[1:]) for i in groups_df["Group_ID"].tolist() if i.startswith("G") and i[1:].isdigit()] if not groups_df.empty else []
            new_gid = f"G{(max(nums) + 1 if nums else 1):03d}"
            append_row_data(WS_GROUPS, [new_gid, gn, my_id, my_id, "", NOW().strftime("%Y-%m-%d")])
            st.success("Tạo nhóm thành công!")

    with sub2:
        st.subheader("📋 Giao Việc Mới")
        my_groups = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
        if my_groups.empty:
            st.warning("Bạn cần tạo nhóm làm trưởng nhóm để giao việc!")
        else:
            task_name = st.text_input("Tên Nhiệm Vụ")
            task_subject = st.text_input("Môn Học")
            
            # Liệt kê thành viên trong các nhóm bạn quản lý
            subs = []
            for _, g in my_groups.iterrows():
                subs.extend([m.strip() for m in str(g["Thành_Viên_IDs"]).split(",") if m.strip()])
            subs = list(set(subs)) # Lọc trùng
            
            assignee = st.selectbox("Giao cho", subs, format_func=lambda x: get_user_name(x, users_df))
            deadline = st.date_input("Hạn chót")
            priority = st.selectbox("Độ ưu tiên", ["Thấp", "Trung bình", "Cao"])
            
            if st.button("🚀 Giao Việc"):
                nums = [int(i[1:]) for i in tasks_df["ID"].tolist() if i.startswith("T") and i[1:].isdigit()] if not tasks_df.empty else []
                new_tid = f"T{(max(nums) + 1 if nums else 1):03d}"
                append_row_data(WS_TASKS, [
                    new_tid, task_name, task_subject, assignee, deadline.strftime("%Y-%m-%d 23:59:00"),
                    priority, "Đang làm", "0", "", "", "", "", NOW().strftime("%Y-%m-%d"), ""
                ])
                st.success("Giao việc thành công!")
        
        st.markdown("---")
        st.subheader("📌 Danh Sách Nhiệm Vụ")
        # Hiển thị bảng Task ở đây
        display_tasks = tasks_df[(tasks_df["Người_Phụ_Trách_ID"] == my_id) | (tasks_df["Người_Phụ_Trách_ID"].isin(subs)) if not my_groups.empty else (tasks_df["Người_Phụ_Trách_ID"] == my_id)]
        if not display_tasks.empty:
            st.dataframe(display_tasks[["ID", "Tên_Công_Việc", "Môn_Học", "Người_Phụ_Trách_ID", "Deadline", "Trạng_Thái", "Tiến_Độ_%"]], use_container_width=True)
        else:
            st.info("Chưa có nhiệm vụ nào liên quan đến bạn.")

# ═══════════════════════════════════════════════════════════
#  6. MAIN APP
# ═══════════════════════════════════════════════════════════
def main_app(data):
    users_df, groups_df, tasks_df = data["users"], data["groups"], data["tasks"]
    my_id = st.session_state["current_user"]["User_ID"]
    
    fresh_user = users_df[users_df["User_ID"] == my_id]
    if fresh_user.empty:
        st.session_state.update({"logged_in": False, "current_user": None})
        st.rerun()
        return
        
    is_leader = not groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id].empty

    with st.sidebar:
        st.markdown("## ⚔️ DEADLINE SLAYER")
        st.success(f"👤 **{fresh_user.iloc[0]['Tên']}**\n\n🆔 ID: `{my_id}`")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state.update({"logged_in": False, "current_user": None})
            st.rerun()

    # ĐÃ XÓA TAB TÀI KHOẢN THEO YÊU CẦU
    t1, t2, t3, t4, t5 = st.tabs(["📊 Dashboard", "👥 Nhóm & Giao Việc", "💬 Chat", "👫 Quản Lý Bạn Bè", "🏆 Xếp Hạng"])

    with t1: render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader)
    with t2: render_network_and_tasks(users_df, groups_df, tasks_df, my_id)
    with t3: st.info("Tính năng Chat đang được hoàn thiện.")
    with t4: st.info("Tính năng Bạn bè đang được hoàn thiện.")
    with t5: st.info("Tính năng Xếp hạng đang được hoàn thiện.")

# ═══════════════════════════════════════════════════════════
#  7. EXECUTE APP
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    app_data = fetch_all_data()
    if not st.session_state.get("logged_in", False):
        show_auth_page(app_data)
    else:
        main_app(app_data)