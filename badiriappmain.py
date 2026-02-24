import streamlit as st
import pandas as pd
from datetime import datetime
import os
import io
import requests
import base64
import json

# Try to load the PowerPoint library securely
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="Marumo Technologies - Badiri App", layout="wide")

DB_FILE = "badiri_db.csv"
USER_FILE = "badiri_users.csv"
SUBTASK_FILE = "badiri_subtasks.csv"
CHAT_FILE = "badiri_chat.csv"
MAIL_FILE = "badiri_mail.csv" 

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

# --- 3. SMART DATA PERSISTENCE ---
def load_data(file, columns):
    if os.path.exists(file):
        df = pd.read_csv(file)
        for col in columns:
            if col not in df.columns:
                if col == "Status": df[col] = "Active" if "User" in file else "Pending"
                elif col == "Role": df[col] = "Standard"
                elif col == "Password": df[col] = "1234" 
                elif col == "Read": df[col] = "No" 
                else: df[col] = ""
        return df
    return pd.DataFrame(columns=columns)

def save_data(df, file):
    df.to_csv(file, index=False)

# Initialize Databases
if "task_db" not in st.session_state: st.session_state.task_db = load_data(DB_FILE, ["Project", "Task Name", "Assignee", "Status", "Date Added", "Due Date", "Comments"])
if "subtask_db" not in st.session_state: st.session_state.subtask_db = load_data(SUBTASK_FILE, ["Project", "Parent Task", "Subtask Name", "Assignee", "Status", "Date Added", "Due Date", "Comments"])
if "user_db" not in st.session_state: st.session_state.user_db = load_data(USER_FILE, ["Full Name", "Email", "Phone Number", "Status", "Role", "Password"])
if "chat_db" not in st.session_state: st.session_state.chat_db = load_data(CHAT_FILE, ["Timestamp", "User", "Message"])
if "mail_db" not in st.session_state: st.session_state.mail_db = load_data(MAIL_FILE, ["Timestamp", "From", "To", "Subject", "Message", "Read"])
if "ai_suggestions" not in st.session_state: st.session_state.ai_suggestions = []
if "chat_ai_suggestions" not in st.session_state: st.session_state.chat_ai_suggestions = [] 

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
                    st.rerun()
                else:
                    st.error("❌ Invalid Credentials")

else:
    with st.sidebar:
        st.header("Badiri App")
        st.caption(f"User: {st.session_state.current_user}")
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()
        st.divider()
        if st.session_state.is_admin:
            st.subheader("👤 Register User")
            with st.form("user_form", clear_on_submit=True):
                u_n = st.text_input("Name")
                u_e = st.text_input("Email")
                u_r = st.selectbox("Role", ["Standard", "Admin", "Viewer Only"])
                u_p = st.text_input("Password", type="password")
                if st.form_submit_button("Create User"):
                    new_u = pd.DataFrame([{"Full Name": u_n, "Email": u_e, "Phone Number": "", "Status": "Active", "Role": u_r, "Password": u_p}])
                    st.session_state.user_db = pd.concat([st.session_state.user_db, new_u], ignore_index=True)
                    save_data(st.session_state.user_db, USER_FILE)
                    st.success("User Created")

    st.title("🛠️ Project Management Dashboard")
    main_col, chat_col = st.columns([3, 1], gap="large")

    with main_col:
        tabs = ["🏠 My Desk"]
        if st.session_state.user_role != "Viewer Only": tabs.append("📋 Workspace")
        tabs.append("📊 Reports")
        if st.session_state.user_role != "Viewer Only": tabs.append("🤖 AI")
        if st.session_state.is_admin: tabs.append("🛡️ Admin")
        
        tab_list = st.tabs(tabs)
        tab_index = 0
        df = st.session_state.task_db
        sub_df_all = st.session_state.subtask_db

        # --- TAB 1: MY DESK ---
        with tab_list[tab_index]:
            st.subheader(f"👋 Welcome, {st.session_state.current_user}!")
            
            # --- INTERNAL MAIL SECTION ---
            st.markdown("### 📧 Internal Mailbox")
            mail_tabs = st.tabs(["📥 Inbox", "📤 Compose Mail"])
            
            with mail_tabs[0]:
                my_mail = st.session_state.mail_db[st.session_state.mail_db["To"] == st.session_state.current_user]
                if my_mail.empty:
                    st.info("Your inbox is empty.")
                else:
                    for idx, row in my_mail.sort_index(ascending=False).iterrows():
                        unread_tag = "🔴 [NEW]" if row["Read"] == "No" else "⚪"
                        with st.expander(f"{unread_tag} {row['Subject']} - From: {row['From']} ({row['Timestamp']})"):
                            st.write(row["Message"])
                            if row["Read"] == "No":
                                if st.button("Mark as Read", key=f"read_{idx}"):
                                    st.session_state.mail_db.at[idx, "Read"] = "Yes"
                                    save_data(st.session_state.mail_db, MAIL_FILE)
                                    st.rerun()

            with mail_tabs[1]:
                with st.form("compose_mail", clear_on_submit=True):
                    to_user = st.selectbox("Send To:", user_list)
                    subject = st.text_input("Subject")
                    msg = st.text_area("Your Message")
                    if st.form_submit_button("Send Mail"):
                        if subject and msg:
                            new_mail = pd.DataFrame([{
                                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "From": st.session_state.current_user,
                                "To": to_user,
                                "Subject": subject,
                                "Message": msg,
                                "Read": "No"
                            }])
                            st.session_state.mail_db = pd.concat([st.session_state.mail_db, new_mail], ignore_index=True)
                            save_data(st.session_state.mail_db, MAIL_FILE)
                            st.success(f"Mail sent to {to_user}!")
                        else:
                            st.error("Please fill in subject and message.")

            st.divider()

            # --- INTERACTIVE INBOX (ACCEPT OR REVERT TASKS) ---
            st.markdown("### ⚡ Inbox: Action Required")
            st.caption("These are new tasks assigned to you. Open them to Accept the work or Revert them to someone else.")
            
            unack_tasks = []
            my_pending_main = df[(df["Assignee"] == st.session_state.current_user) & (df["Status"] == "Pending")]
            my_pending_sub = sub_df_all[(sub_df_all["Assignee"] == st.session_state.current_user) & (sub_df_all["Status"] == "Pending")]
            
            for real_idx, row in my_pending_main.iterrows():
                unack_tasks.append({"Type": "Main", "Idx": real_idx, "Project": row["Project"], "Name": row["Task Name"], "Due": row["Due Date"], "Comments": str(row["Comments"])})
            for real_idx, row in my_pending_sub.iterrows():
                unack_tasks.append({"Type": "Sub", "Idx": real_idx, "Project": row["Project"], "Name": row["Subtask Name"], "Due": row["Due Date"], "Comments": str(row["Comments"])})

            if len(unack_tasks) == 0:
                st.info("✅ Inbox Zero! You have no new tasks waiting.")
            else:
                for t in unack_tasks:
                    with st.expander(f"🔴 NEW ASSIGNMENT: {t['Project']} - {t['Name']} (Due: {t['Due']})"):
                        st.write(f"**Current Notes:** {t['Comments'] if pd.notna(t['Comments']) and t['Comments'].strip() else 'No notes provided.'}")
                        
                        with st.form(f"inbox_form_{t['Type']}_{t['Idx']}"):
                            action = st.radio("What would you like to do?", ["✅ Accept Task (Move to In Progress)", "↩️ Revert Task (Reassign to someone else)"], horizontal=True)
                            
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
                                        save_data(st.session_state.task_db, DB_FILE)
                                    else:
                                        st.session_state.subtask_db.at[t['Idx'], "Status"] = "In Progress"
                                        st.session_state.subtask_db.at[t['Idx'], "Comments"] = new_cmt
                                        save_data(st.session_state.subtask_db, SUBTASK_FILE)
                                    
                                    st.success("Task Accepted and moved to your active workspace!")
                                    st.rerun()
                                    
                                else:
                                    note_text = notes.strip() if notes.strip() else "Task reverted."
                                    new_cmt = base_cmt + f"\n[{timestamp}] {st.session_state.current_user} REVERTED to {revert_user}: {note_text}"
                                    
                                    if t['Type'] == "Main":
                                        st.session_state.task_db.at[t['Idx'], "Assignee"] = revert_user
                                        st.session_state.task_db.at[t['Idx'], "Comments"] = new_cmt
                                        save_data(st.session_state.task_db, DB_FILE)
                                    else:
                                        st.session_state.subtask_db.at[t['Idx'], "Assignee"] = revert_user
                                        st.session_state.subtask_db.at[t['Idx'], "Comments"] = new_cmt
                                        save_data(st.session_state.subtask_db, SUBTASK_FILE)
                                        
                                    st.success(f"Task Reverted and sent to {revert_user}!")
                                    st.rerun()

            st.divider()
            
            # --- ACTIVE TASKS (IN PROGRESS) ---
            st.markdown("### 🏃‍♂️ Tasks In Progress")
            my_active_main = df[(df["Assignee"] == st.session_state.current_user) & (df["Status"] == "In Progress")]
            my_active_sub = sub_df_all[(sub_df_all["Assignee"] == st.session_state.current_user) & (sub_df_all["Status"] == "In Progress")]
            
            if my_active_main.empty and my_active_sub.empty:
                st.info("You don't have any active tasks currently in progress.")
            else:
                if not my_active_main.empty: 
                    st.markdown("**Main Tasks:**")
                    st.dataframe(my_active_main[["Project", "Task Name", "Status", "Due Date"]], hide_index=True, use_container_width=True)
                if not my_active_sub.empty: 
                    st.markdown("**Subtasks:**")
                    st.dataframe(my_active_sub[["Project", "Parent Task", "Subtask Name", "Status", "Due Date"]], hide_index=True, use_container_width=True)

                st.markdown("##### 📝 Update Active Task Progress")
                active_options = []
                for real_idx, row in my_active_main.iterrows():
                    active_options.append(f"[Main] {row['Project']} - {row['Task Name']}")
                for real_idx, row in my_active_sub.iterrows():
                    active_options.append(f"[Sub] {row['Project']} - {row['Subtask Name']}")
                    
                selected_active = st.selectbox("Select active task to log progress or complete:", ["-- Select --"] + active_options)
                
                if selected_active != "-- Select --":
                    is_main = selected_active.startswith("[Main]")
                    clean_label = selected_active.split("] ", 1)[1]
                    
                    if is_main:
                        matched = my_active_main[my_active_main["Project"] + " - " + my_active_main["Task Name"] == clean_label]
                        real_idx = matched.index[0]
                        curr_status = df.at[real_idx, "Status"]
                        curr_comments = str(df.at[real_idx, "Comments"]) if pd.notna(df.at[real_idx, "Comments"]) else ""
                    else:
                        matched = my_active_sub[my_active_sub["Project"] + " - " + my_active_sub["Subtask Name"] == clean_label]
                        real_idx = matched.index[0]
                        curr_status = sub_df_all.at[real_idx, "Status"]
                        curr_comments = str(sub_df_all.at[real_idx, "Comments"]) if pd.notna(sub_df_all.at[real_idx, "Comments"]) else ""
                        
                    with st.form("update_active_form"):
                        new_status = st.selectbox("Update Status", ["In Progress", "Completed"])
                        added_comment = st.text_area("Add a progress update / final notes:")
                        
                        if st.form_submit_button("💾 Save Progress"):
                            final_comments = curr_comments
                            if added_comment.strip():
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                                final_comments = final_comments.strip() + f"\n[{timestamp}] {st.session_state.current_user}: {added_comment.strip()}"
                                
                            if is_main:
                                st.session_state.task_db.at[real_idx, "Status"] = new_status
                                st.session_state.task_db.at[real_idx, "Comments"] = final_comments
                                save_data(st.session_state.task_db, DB_FILE)
                            else:
                                st.session_state.subtask_db.at[real_idx, "Status"] = new_status
                                st.session_state.subtask_db.at[real_idx, "Comments"] = final_comments
                                save_data(st.session_state.subtask_db, SUBTASK_FILE)
                                
                            st.success("Task progress saved!")
                            st.rerun()
        tab_index += 1

        # --- TAB 2: WORKSPACE ---
        if st.session_state.user_role != "Viewer Only":
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
                    else: st.dataframe(proj_df, hide_index=True, use_container_width=True) 
                        
                    with st.expander("📝 Main Tasks", expanded=True):
                        add_col, edit_col = st.columns(2)
                        with add_col:
                            with st.form("workspace_add_task_form", clear_on_submit=True):
                                t_name = st.text_input("Task Name")
                                t_assignee = st.selectbox("Assign To", user_list)
                                t_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
                                t_due = st.date_input("Due Date")
                                t_comments = st.text_area("Comments")
                                if st.form_submit_button("Add Task") and t_name:
                                    new_task = pd.DataFrame([{"Project": active_project, "Task Name": t_name, "Assignee": t_assignee, "Status": t_status, "Date Added": datetime.now().strftime("%Y-%m-%d"), "Due Date": str(t_due), "Comments": t_comments}])
                                    st.session_state.task_db = pd.concat([st.session_state.task_db, new_task], ignore_index=True)
                                    save_data(st.session_state.task_db, DB_FILE)
                                    st.rerun()
                        with edit_col:
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
                                            if new_assignee != curr_assig: new_comments += f"\n[Forwarded to {new_assignee}]"
                                            st.session_state.task_db.at[selected_idx, "Assignee"] = new_assignee
                                            st.session_state.task_db.at[selected_idx, "Status"] = new_status
                                            st.session_state.task_db.at[selected_idx, "Comments"] = new_comments
                                            save_data(st.session_state.task_db, DB_FILE)
                                            st.rerun()

                    with st.expander("🗂️ Subtasks", expanded=False):
                        if not proj_df.empty:
                            parent_task = st.selectbox("Select Main Task:", ["-- Select --"] + proj_df["Task Name"].tolist())
                            if parent_task != "-- Select --":
                                active_subtasks = sub_df_all[(sub_df_all["Project"] == active_project) & (sub_df_all["Parent Task"] == parent_task)]
                                if not active_subtasks.empty: st.dataframe(active_subtasks.drop(columns=["Project", "Parent Task"], errors="ignore"), hide_index=True, use_container_width=True) 
                                
                                s_add_col, s_edit_col = st.columns(2)
                                with s_add_col:
                                    with st.form("add_sub_form", clear_on_submit=True):
                                        s_name = st.text_input("Subtask Name")
                                        s_assignee = st.selectbox("Assign To", user_list)
                                        s_due = st.date_input("Due Date")
                                        if st.form_submit_button("Add Subtask") and s_name:
                                            new_sub = pd.DataFrame([{"Project": active_project, "Parent Task": parent_task, "Subtask Name": s_name, "Assignee": s_assignee, "Status": "Pending", "Date Added": datetime.now().strftime("%Y-%m-%d"), "Due Date": str(s_due), "Comments": ""}])
                                            st.session_state.subtask_db = pd.concat([st.session_state.subtask_db, new_sub], ignore_index=True)
                                            save_data(st.session_state.subtask_db, SUBTASK_FILE)
                                            st.rerun()
                                with s_edit_col:
                                    if not active_subtasks.empty:
                                        sub_dict = {idx: row["Subtask Name"] for idx, row in active_subtasks.iterrows()}
                                        sub_idx = st
