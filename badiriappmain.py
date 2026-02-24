import streamlit as st
import pandas as pd
from datetime import datetime
import os
import io
import requests
import base64
import json
import sqlite3

# Try to load the PowerPoint library securely
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

# Try to load Plotly for the Calendar Timeline
try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Marumo Technologies - Badiri App", layout="wide")

DB_NAME = "badiri_backend.db"
os.makedirs("attachments", exist_ok=True) # Ensure attachment folder exists

# --- 2. POWERPOINT GENERATOR ---
def create_ppt(df, sub_df):
    prs = Presentation()
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = "Badiri App Status Report"
    title_slide.placeholders[1].text = f"Marumo Technologies\nGenerated on {datetime.now().strftime('%Y-%m-%d')}"
    
    metrics_slide = prs.slides.add_slide(prs.slide_layouts[1])
    metrics_slide.shapes.title.text = "Executive Summary"
    tf = metrics_slide.shapes.placeholders[1].text_frame
    total = len(df)
    completed = len(df[df["Status"] == "Completed"])
    pending = len(df[df["Status"] == "Pending"])
    tf.text = f"Total Main Tasks: {total}"
    p1 = tf.add_paragraph()
    p1.text = f"✅ Completed Tasks: {completed}"
    p2 = tf.add_paragraph()
    p2.text = f"⏳ Pending Tasks: {pending}"
    
    ppt_stream = io.BytesIO()
    prs.save(ppt_stream)
    ppt_stream.seek(0)
    return ppt_stream

# --- 3. DATABASE ENGINE ---
def init_db_migration():
    conn = sqlite3.connect(DB_NAME)
    
    csv_mapping = {
        "tasks": "badiri_db.csv",
        "subtasks": "badiri_subtasks.csv",
        "users": "badiri_users.csv",
        "chat": "badiri_chat.csv",
        "mail": "badiri_mail.csv"
    }
    
    for table_name, csv_file in csv_mapping.items():
        if os.path.exists(csv_file):
            try:
                check = pd.read_sql(f"SELECT count(*) FROM {table_name}", conn)
                if check.iloc[0,0] > 0: continue 
            except: pass 
            
            df = pd.read_csv(csv_file)
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            os.rename(csv_file, f"{csv_file}.backup")
    conn.close()

init_db_migration()

def load_data(table_name, default_columns):
    conn = sqlite3.connect(DB_NAME)
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    except:
        df = pd.DataFrame(columns=default_columns)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    
    for col in default_columns:
        if col not in df.columns:
            if col == "Status": df[col] = "Active" if table_name == "users" else "Pending"
            elif col == "Role": df[col] = "Standard"
            elif col == "Password": df[col] = "1234" 
            elif col == "Read": df[col] = "No" 
            else: df[col] = ""
    return df

def save_data(df, table_name):
    conn = sqlite3.connect(DB_NAME)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()

def show_inline_msg(location):
    if "inline_msg" in st.session_state and st.session_state.inline_msg.get("loc") == location:
        st.success(st.session_state.inline_msg["msg"])
        st.session_state.inline_msg = {} 

if "task_db" not in st.session_state: st.session_state.task_db = load_data("tasks", ["Project", "Task Name", "Assignee", "Status", "Date Added", "Due Date", "Comments", "Attachments"])
if "subtask_db" not in st.session_state: st.session_state.subtask_db = load_data("subtasks", ["Project", "Parent Task", "Subtask Name", "Assignee", "Status", "Date Added", "Due Date", "Comments", "Attachments"])
if "user_db" not in st.session_state: st.session_state.user_db = load_data("users", ["Full Name", "Email", "Phone Number", "Status", "Role", "Password"])
if "chat_db" not in st.session_state: st.session_state.chat_db = load_data("chat", ["Timestamp", "User", "Message"])
if "mail_db" not in st.session_state: st.session_state.mail_db = load_data("mail", ["Timestamp", "From", "To", "Subject", "Message", "Read"])
if "ai_suggestions" not in st.session_state: st.session_state.ai_suggestions = []
if "chat_ai_suggestions" not in st.session_state: st.session_state.chat_ai_suggestions = [] 
if "plan_ai_suggestions" not in st.session_state: st.session_state.plan_ai_suggestions = [] 
if "inline_msg" not in st.session_state: st.session_state.inline_msg = {}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.user_role = "Standard"
    st.session_state.is_admin = False

active_users = st.session_state.user_db[st.session_state.user_db["Status"] == "Active"] if not st.session_state.user_db.empty else pd.DataFrame()
user_list = active_users["Full Name"].tolist() if not active_users.empty else ["Unassigned"]

# --- 4. MAIN APP ROUTING ---
if not st.session_state.logged_in:
    st.title("🔒 Login to Badiri App")
    st.markdown("Welcome to the Marumo Technologies workspace.")
    with st.form("login_form"):
        email_input = st.text_input("Email Address")
        pass_input = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if email_input.strip().lower() == "admin" and pass_input == "Admin123":
                st.session_state.logged_in = True
                st.session_state.current_user = "Master Admin"
                st.session_state.user_role = "Admin"
                st.session_state.is_admin = True
                st.session_state.inline_msg = {"loc": "top", "msg": "✅ Logged in successfully as Master Admin!"}
                st.rerun()
            else:
                safe_db = st.session_state.user_db.copy()
                safe_db["Email"] = safe_db["Email"].astype(str).str.strip().str.lower()
                safe_db["Password"] = safe_db["Password"].astype(str).str.strip()
                user_match = safe_db[(safe_db["Email"] == email_input.strip().lower()) & (safe_db["Password"] == pass_input.strip()) & (safe_db["Status"] == "Active")]
                if not user_match.empty:
                    idx = user_match.index[0]
                    st.session_state.logged_in = True
                    st.session_state.current_user = st.session_state.user_db.at[idx, "Full Name"]
                    st.session_state.user_role = st.session_state.user_db.at[idx, "Role"]
                    st.session_state.is_admin = (st.session_state.user_role == "Admin")
                    st.session_state.inline_msg = {"loc": "top", "msg": f"✅ Welcome back, {st.session_state.current_user}!"}
                    st.rerun()
                else:
                    st.error("❌ Invalid Credentials")

else:
    with st.sidebar:
        st.header("Badiri App")
        st.caption(f"User: {st.session_state.current_user}")
        
        unread_count = len(st.session_state.mail_db[(st.session_state.mail_db["To"] == st.session_state.current_user) & (st.session_state.mail_db["Read"] == "No")])
        if unread_count > 0:
            st.error(f"📬 {unread_count} Unread Mail(s)")
            
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()
        st.divider()
        if st.session_state.is_admin:
            st.subheader("👤 Register User")
            show_inline_msg("sidebar_admin") 
            with st.form("user_form", clear_on_submit=True):
                u_n = st.text_input("Name")
                u_e = st.text_input("Email")
                u_r = st.selectbox("Role", ["Standard", "Admin", "Viewer Only"])
                u_p = st.text_input("Password", type="password")
                if st.form_submit_button("Create User"):
                    new_u = pd.DataFrame([{"Full Name": u_n, "Email": u_e, "Phone Number": "", "Status": "Active", "Role": u_r, "Password": u_p}])
                    st.session_state.user_db = pd.concat([st.session_state.user_db, new_u], ignore_index=True)
                    save_data(st.session_state.user_db, "users")
                    st.session_state.inline_msg = {"loc": "sidebar_admin", "msg": f"✅ New user '{u_n}' created!"}
                    st.rerun()

    st.title("🛠️ Project Management Dashboard")
    show_inline_msg("top") 
    st.divider()

    tabs = ["🏠 My Desk"]
    if st.session_state.user_role != "Viewer Only": tabs.append("📋 Workspace")
    tabs.append("📅 Project Calendar")
    tabs.append("📊 Reports")
    tabs.append("💬 Team Communications")
    if st.session_state.user_role != "Viewer Only": tabs.append("🧠 AI Project Manager")
    if st.session_state.is_admin: tabs.append("🛡️ Admin")
    
    tab_list = st.tabs(tabs)
    tab_index = 0
    df = st.session_state.task_db
    sub_df_all = st.session_state.subtask_db

    # --- TAB 1: MY DESK ---
    with tab_list[tab_index]:
        st.subheader(f"👋 Welcome, {st.session_state.current_user}!")
        st.write("") 
        
        my_main = df[(df["Assignee"] == st.session_state.current_user) & (df["Status"] != "Completed")]
        my_sub = sub_df_all[(sub_df_all["Assignee"] == st.session_state.current_user) & (sub_df_all["Status"] != "Completed")]
        
        inbox_tasks = []
        active_tasks = []
        
        for real_idx, row in my_main.iterrows():
            is_unacknowledged = (row['Status'] == "Pending" and st.session_state.current_user not in str(row['Comments']))
            t_data = {"Type": "Main", "Idx": real_idx, "Project": row["Project"], "Name": row["Task Name"], "Status": row["Status"], "Due": row["Due Date"], "Comments": str(row["Comments"]), "Attachments": str(row.get("Attachments", ""))}
            if is_unacknowledged: inbox_tasks.append(t_data)
            else: active_tasks.append(t_data)
            
        for real_idx, row in my_sub.iterrows():
            is_unacknowledged = (row['Status'] == "Pending" and st.session_state.current_user not in str(row['Comments']))
            t_data = {"Type": "Sub", "Idx": real_idx, "Project": row["Project"], "Name": row["Subtask Name"], "Status": row["Status"], "Due": row["Due Date"], "Comments": str(row["Comments"]), "Attachments": str(row.get("Attachments", ""))}
            if is_unacknowledged: inbox_tasks.append(t_data)
            else: active_tasks.append(t_data)

        # --- 1. INBOX SECTION ---
        st.markdown("### ⚡ Inbox: Action Required")
        show_inline_msg("desk_inbox") 
        st.caption("These are new assignments. Open them to Accept the work or Revert to someone else.")
        
        if len(inbox_tasks) == 0:
            st.info("✅ Inbox Zero! You have no new tasks waiting.")
        else:
            for t in inbox_tasks:
                with st.expander(f"🔴 NEW: {t['Project']} - {t['Name']} (Due: {t['Due']})"):
                    st.write(f"**Current Notes:** {t['Comments'] if pd.notna(t['Comments']) and t['Comments'].strip() and t['Comments'] != 'nan' else 'No notes provided.'}")
                    with st.form(f"inbox_form_{t['Type']}_{t['Idx']}"):
                        action = st.radio("Action:", ["✅ Accept Task (Move to Workspace)", "↩️ Revert Task (Reassign)"], horizontal=True)
                        c1, c2 = st.columns(2)
                        revert_user = c1.selectbox("If reverting, send to:", user_list)
                        notes = c2.text_input("Add a comment / reason:")
                        
                        if st.form_submit_button("Confirm Action"):
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                            base_cmt = t['Comments'] if pd.notna(t['Comments']) and t['Comments'].strip() != "nan" else ""
                            
                            if "Accept" in action:
                                note_text = notes.strip() if notes.strip() else "Task formally accepted."
                                new_cmt = base_cmt + f"\n[{timestamp}] {st.session_state.current_user} ACCEPTED: {note_text}"
                                if t['Type'] == "Main":
                                    st.session_state.task_db.at[t['Idx'], "Status"] = "In Progress"
                                    st.session_state.task_db.at[t['Idx'], "Comments"] = new_cmt
                                    save_data(st.session_state.task_db, "tasks")
                                else:
                                    st.session_state.subtask_db.at[t['Idx'], "Status"] = "In Progress"
                                    st.session_state.subtask_db.at[t['Idx'], "Comments"] = new_cmt
                                    save_data(st.session_state.subtask_db, "subtasks")
                                
                                st.session_state.inline_msg = {"loc": "desk_inbox", "msg": f"✅ Task '{t['Name']}' Accepted and moved to your active workspace!"}
                                st.rerun()
                            else:
                                note_text = notes.strip() if notes.strip() else "Task reverted."
                                new_cmt = base_cmt + f"\n[{timestamp}] {st.session_state.current_user} REVERTED to {revert_user}: {note_text}"
                                if t['Type'] == "Main":
                                    st.session_state.task_db.at[t['Idx'], "Assignee"] = revert_user
                                    st.session_state.task_db.at[t['Idx'], "Comments"] = new_cmt
                                    save_data(st.session_state.task_db, "tasks")
                                else:
                                    st.session_state.subtask_db.at[t['Idx'], "Assignee"] = revert_user
                                    st.session_state.subtask_db.at[t['Idx'], "Comments"] = new_cmt
                                    save_data(st.session_state.subtask_db, "subtasks")
                                    
                                st.session_state.inline_msg = {"loc": "desk_inbox", "msg": f"✅ Task Reverted and reassigned to {revert_user}!"}
                                st.rerun()

        st.divider()
        
        # --- 2. ACTIVE PENDING TASKS ---
        st.markdown("### 📌 My Pending Tasks")
        show_inline_msg("desk_active") 
        st.caption("Click on any task below to log your progress, add receipts/files, or complete it.")
        
        if len(active_tasks) == 0:
            st.info("You don't have any active tasks currently in progress.")
        else:
            for t in active_tasks:
                icon = "⏳" if t['Status'] == "Pending" else "🚀"
                with st.expander(f"{icon} [{t['Type']}] {t['Project']} - {t['Name']} ({t['Status']})"):
                    st.write(f"**Due Date:** {t['Due']}")
                    st.write(f"**Current Notes:**\n{t['Comments'] if pd.notna(t['Comments']) and t['Comments'].strip() and t['Comments'] != 'nan' else 'No notes provided.'}")
                    
                    if pd.notna(t['Attachments']) and t['Attachments'] != "" and t['Attachments'] != "nan":
                        st.markdown("**📎 Task Attachments:**")
                        att_files = t['Attachments'].split('|')
                        for file_path in att_files:
                            if os.path.exists(file_path):
                                with open(file_path, "rb") as f:
                                    st.download_button(label=f"⬇️ Download {os.path.basename(file_path).split('_', 1)[-1]}", data=f, file_name=os.path.basename(file_path).split('_', 1)[-1], key=f"dl_{t['Type']}_{t['Idx']}_{file_path}")
                    
                    st.write("")
                    with st.form(f"update_active_{t['Type']}_{t['Idx']}"):
                        new_status = st.selectbox("Update Status", ["Pending", "In Progress", "Completed"], index=["Pending", "In Progress", "Completed"].index(t['Status']))
                        added_comment = st.text_area("Add a progress update / final notes:")
                        
                        uploaded_file = st.file_uploader("Upload Document / Receipt (Optional)")
                        
                        if st.form_submit_button("💾 Save Progress"):
                            final_comments = t['Comments'] if pd.notna(t['Comments']) and t['Comments'].strip() != "nan" else ""
                            if added_comment.strip():
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                                final_comments = final_comments.strip() + f"\n[{timestamp}] {st.session_state.current_user}: {added_comment.strip()}"
                                
                            final_atts = t['Attachments'] if pd.notna(t['Attachments']) and t['Attachments'] != "nan" else ""
                            if uploaded_file is not None:
                                safe_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name.replace('|', '')}"
                                file_path = os.path.join("attachments", safe_filename)
                                with open(file_path, "wb") as f:
                                    f.write(uploaded_file.getbuffer())
                                final_atts = file_path if not final_atts else final_atts + "|" + file_path
                                
                            if t['Type'] == "Main":
                                st.session_state.task_db.at[t['Idx'], "Status"] = new_status
                                st.session_state.task_db.at[t['Idx'], "Comments"] = final_comments
                                st.session_state.task_db.at[t['Idx'], "Attachments"] = final_atts
                                save_data(st.session_state.task_db, "tasks")
                            else:
                                st.session_state.subtask_db.at[t['Idx'], "Status"] = new_status
                                st.session_state.subtask_db.at[t['Idx'], "Comments"] = final_comments
                                st.session_state.subtask_db.at[t['Idx'], "Attachments"] = final_atts
                                save_data(st.session_state.subtask_db, "subtasks")
                                
                            st.session_state.inline_msg = {"loc": "desk_active", "msg": f"✅ Progress saved for '{t['Name']}'! Status: {new_status}"}
                            st.rerun()

                    if t['Type'] == "Main":
                        st.markdown("---")
                        st.markdown("##### ➕ Create Subtask")
                        with st.form(f"quick_add_sub_{t['Idx']}"):
                            s_name = st.text_input("Subtask Name")
                            c1, c2 = st.columns(2)
                            default_user_idx = user_list.index(st.session_state.current_user) if st.session_state.current_user in user_list else 0
                            s_assignee = c1.selectbox("Assign To", user_list, index=default_user_idx)
                            s_due = c2.date_input("Due Date")
                            
                            if st.form_submit_button("Create Subtask"):
                                if s_name:
                                    new_sub = pd.DataFrame([{
                                        "Project": t['Project'], 
                                        "Parent Task": t['Name'], 
                                        "Subtask Name": s_name, 
                                        "Assignee": s_assignee, 
                                        "Status": "Pending", 
                                        "Date Added": datetime.now().strftime("%Y-%m-%d"), 
                                        "Due Date": str(s_due), 
                                        "Comments": "",
                                        "Attachments": ""
                                    }])
                                    st.session_state.subtask_db = pd.concat([st.session_state.subtask_db, new_sub], ignore_index=True)
                                    save_data(st.session_state.subtask_db, "subtasks")
                                    st.session_state.inline_msg = {"loc": "desk_active", "msg": f"✅ Subtask '{s_name}' created under '{t['Name']}'!"}
                                    st.rerun()
                                else:
                                    st.error("Please provide a subtask name.")

    # --- TAB 2: WORKSPACE ---
    if st.session_state.user_role != "Viewer Only":
        tab_index += 1
        with tab_list[tab_index]:
            st.subheader("📁 Project Workspace")
            existing_projects = df["Project"].unique().tolist() if not df.empty else []
            project_selection = st.selectbox("Select Workspace", ["-- Choose a Project --", "✨ New Project"] + existing_projects)

            active_project = st.text_input("Enter New Project Name") if project_selection == "✨ New Project" else (project_selection if project_selection != "-- Choose a Project --" else None)

            if active_project:
                st.divider()
                st.markdown(f"### 📂 {active_project}")
                proj_df = df[df["Project"] == active_project].drop(columns=["Due Date parsed"], errors='ignore')
                
                if proj_df.empty: st.info("No tasks yet.")
                else: st.dataframe(proj_df[["Task Name", "Assignee", "Status", "Due Date"]], hide_index=True, use_container_width=True) 
                    
                with st.expander("📝 Main Tasks", expanded=True):
                    add_col, edit_col = st.columns(2)
                    with add_col:
                        show_inline_msg("ws_add_main") 
                        with st.form("workspace_add_task_form", clear_on_submit=True):
                            t_name = st.text_input("Task Name")
                            t_assignee = st.selectbox("Assign To", user_list)
                            t_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
                            t_due = st.date_input("Due Date")
                            t_comments = st.text_area("Comments")
                            if st.form_submit_button("Add Task") and t_name:
                                new_task = pd.DataFrame([{"Project": active_project, "Task Name": t_name, "Assignee": t_assignee, "Status": t_status, "Date Added": datetime.now().strftime("%Y-%m-%d"), "Due Date": str(t_due), "Comments": t_comments, "Attachments": ""}])
                                st.session_state.task_db = pd.concat([st.session_state.task_db, new_task], ignore_index=True)
                                save_data(st.session_state.task_db, "tasks")
                                st.session_state.inline_msg = {"loc": "ws_add_main", "msg": f"✅ New task '{t_name}' added to workspace!"}
                                st.rerun()
                    with edit_col:
                        show_inline_msg("ws_upd_main") 
                        if not proj_df.empty:
                            task_dict = {idx: row["Task Name"] for idx, row in proj_df.iterrows()}
                            selected_idx = st.selectbox("Update Task", options=list(task_dict.keys()), format_func=lambda x: task_dict[x])
                            if selected_idx is not None:
                                curr_assig = df.at[selected_idx, "Assignee"]
                                with st.form("workspace_update_form"):
                                    new_assignee = st.selectbox("Reassign To", user_list, index=user_list.index(curr_assig) if curr_assig in user_list else 0)
                                    new_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
                                    new_comments = st.text_area("Comments", value=str(df.at[selected_idx, "Comments"]))
                                    if st.form_submit_button("Save Updates"):
                                        if new_assignee != curr_assig: 
                                            new_comments += f"\n[Forwarded to {new_assignee}]"
                                        st.session_state.task_db.at[selected_idx, "Assignee"] = new_assignee
                                        st.session_state.task_db.at[selected_idx, "Status"] = new_status
                                        st.session_state.task_db.at[selected_idx, "Comments"] = new_comments
                                        save_data(st.session_state.task_db, "tasks")
                                        st.session_state.inline_msg = {"loc": "ws_upd_main", "msg": "✅ Task successfully updated!"}
                                        st.rerun()

                with st.expander("🗂️ Subtasks", expanded=False):
                    if not proj_df.empty:
                        parent_task = st.selectbox("Select Main Task:", ["-- Select --"] + proj_df["Task Name"].tolist())
                        if parent_task != "-- Select --":
                            active_subtasks = sub_df_all[(sub_df_all["Project"] == active_project) & (sub_df_all["Parent Task"] == parent_task)]
                            if not active_subtasks.empty: st.dataframe(active_subtasks[["Subtask Name", "Assignee", "Status", "Due Date"]], hide_index=True, use_container_width=True) 
                            
                            s_add_col, s_edit_col = st.columns(2)
                            with s_add_col:
                                show_inline_msg("ws_add_sub") 
                                with st.form("add_sub_form", clear_on_submit=True):
                                    s_name = st.text_input("Subtask Name")
                                    s_assignee = st.selectbox("Assign To", user_list)
                                    s_due = st.date_input("Due Date")
                                    if st.form_submit_button("Add Subtask") and s_name:
                                        new_sub = pd.DataFrame([{"Project": active_project, "Parent Task": parent_task, "Subtask Name": s_name, "Assignee": s_assignee, "Status": "Pending", "Date Added": datetime.now().strftime("%Y-%m-%d"), "Due Date": str(s_due), "Comments": "", "Attachments": ""}])
                                        st.session_state.subtask_db = pd.concat([st.session_state.subtask_db, new_sub], ignore_index=True)
                                        save_data(st.session_state.subtask_db, "subtasks")
                                        st.session_state.inline_msg = {"loc": "ws_add_sub", "msg": f"✅ New subtask '{s_name}' added!"}
                                        st.rerun()
                            with s_edit_col:
                                show_inline_msg("ws_upd_sub") 
                                if not active_subtasks.empty:
                                    sub_dict = {idx: row["Subtask Name"] for idx, row in active_subtasks.iterrows()}
                                    sub_idx = st.selectbox("Update Subtask", options=list(sub_dict.keys()), format_func=lambda x: sub_dict[x])
                                    if sub_idx is not None:
                                        with st.form("update_sub_form"):
                                            new_s_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
                                            if st.form_submit_button("Save Subtask"):
                                                st.session_state.subtask_db.at[sub_idx, "Status"] = new_s_status
                                                save_data(st.session_state.subtask_db, "subtasks")
                                                st.session_state.inline
