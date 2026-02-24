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

# --- 2. POWERPOINT GENERATOR FUNCTION ---
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
    
    tf.text = f"Total Projects & Main Tasks: {total}"
    p1 = tf.add_paragraph()
    p1.text = f"✅ Completed Tasks: {completed}"
    p2 = tf.add_paragraph()
    p2.text = f"⏳ Pending Tasks: {pending}"
    
    projects = df["Project"].unique()
    if len(projects) > 0:
        health_slide = prs.slides.add_slide(prs.slide_layouts[5])
        health_slide.shapes.title.text = "Project Health Dashboard"
        display_projects = projects[:10] 
        rows, cols = len(display_projects) + 1, 4
        table_shape = health_slide.shapes.add_table(rows, cols, Inches(0.5), Inches(1.5), Inches(9.0), Inches(0.8)).table
        headers = ["Project Name", "Total Tasks", "Completed", "Completion %"]
        for i, h in enumerate(headers): table_shape.cell(0, i).text = h
        for r_idx, proj in enumerate(display_projects):
            p_df = df[df["Project"] == proj]
            p_tot = len(p_df)
            p_comp = len(p_df[p_df["Status"] == "Completed"])
            p_pct = f"{int((p_comp / p_tot) * 100)}%" if p_tot > 0 else "0%"
            table_shape.cell(r_idx + 1, 0).text = str(proj)
            table_shape.cell(r_idx + 1, 1).text = str(p_tot)
            table_shape.cell(r_idx + 1, 2).text = str(p_comp)
            table_shape.cell(r_idx + 1, 3).text = p_pct

    calc_df = df.copy()
    calc_df['Safe Date'] = pd.to_datetime(calc_df['Due Date'], errors='coerce')
    today_ts = pd.Timestamp.now().normalize()
    overdue_df = calc_df[(calc_df["Safe Date"] < today_ts) & (calc_df["Status"] != "Completed")]
    
    if not overdue_df.empty:
        overdue_df['Days Overdue'] = (today_ts - overdue_df['Safe Date']).dt.days
        display_overdue = overdue_df.head(10) 
        od_slide = prs.slides.add_slide(prs.slide_layouts[5])
        od_slide.shapes.title.text = "Bottleneck & Overdue Report"
        rows, cols = len(display_overdue) + 1, 4
        table_shape = od_slide.shapes.add_table(rows, cols, Inches(0.5), Inches(1.5), Inches(9.0), Inches(0.8)).table
        headers = ["Project", "Task Name", "Assignee", "Days Overdue"]
        for i, h in enumerate(headers): table_shape.cell(0, i).text = h
        for r_idx, (_, row) in enumerate(display_overdue.iterrows()):
            table_shape.cell(r_idx + 1, 0).text = str(row['Project'])
            table_shape.cell(r_idx + 1, 1).text = str(row['Task Name'])
            table_shape.cell(r_idx + 1, 2).text = str(row['Assignee'])
            table_shape.cell(r_idx + 1, 3).text = f"{int(row['Days Overdue'])} Days"

    if not df.empty or not sub_df.empty:
        main_perf = df[["Assignee", "Status"]] if not df.empty else pd.DataFrame(columns=["Assignee", "Status"])
        sub_perf = sub_df[["Assignee", "Status"]] if not sub_df.empty else pd.DataFrame(columns=["Assignee", "Status"])
        comb_df = pd.concat([main_perf, sub_perf], ignore_index=True)
        users = comb_df["Assignee"].dropna().unique()
        if len(users) > 0:
            display_users = users[:10] 
            perf_slide = prs.slides.add_slide(prs.slide_layouts[5])
            perf_slide.shapes.title.text = "Team Performance & Capacity Matrix"
            rows, cols = len(display_users) + 1, 4
            table_shape = perf_slide.shapes.add_table(rows, cols, Inches(0.5), Inches(1.5), Inches(9.0), Inches(0.8)).table
            headers = ["Team Member", "Total Workload", "Completed", "Efficiency Rate"]
            for i, h in enumerate(headers): table_shape.cell(0, i).text = h
            for r_idx, user in enumerate(display_users):
                u_df = comb_df[comb_df["Assignee"] == user]
                u_tot = len(u_df)
                u_comp = len(u_df[u_df["Status"] == "Completed"])
                u_pct = f"{int((u_comp / u_tot) * 100)}%" if u_tot > 0 else "0%"
                table_shape.cell(r_idx + 1, 0).text = str(user)
                table_shape.cell(r_idx + 1, 1).text = str(u_tot)
                table_shape.cell(r_idx + 1, 2).text = str(u_comp)
                table_shape.cell(r_idx + 1, 3).text = u_pct

    ppt_stream = io.BytesIO()
    prs.save(ppt_stream)
    ppt_stream.seek(0)
    return ppt_stream

# --- 3. UI RENDERING FUNCTIONS ---
def render_table(df, bg_color="transparent"):
    if df.empty:
        st.write("No records found.")
        return
    markdown = f"| {' | '.join(df.columns)} |\n"
    markdown += f"|{'|'.join(['---'] * len(df.columns))}|\n"
    for _, row in df.iterrows():
        clean_row = [str(x).replace('|', '-').replace('\n', ' <br> ') for x in row.values]
        markdown += f"| {' | '.join(clean_row)} |\n"
    st.markdown(f'<div style="background-color: {bg_color}; padding: 15px; border-radius: 8px;">\n\n{markdown}\n\n</div>', unsafe_allow_html=True)

def render_chat_bubble(user, msg, time, is_me):
    bg_color = "#dbeafe" if is_me else "#f1f5f9"
    text_color = "#1e40af" if is_me else "#334155"
    align = "right" if is_me else "left"
    name = "You" if is_me else user
    
    html = f"""
    <div style="text-align: {align}; margin-bottom: 10px;">
        <div style="display: inline-block; background-color: {bg_color}; color: {text_color}; padding: 8px 12px; border-radius: 12px; max-width: 90%; text-align: left;">
            <span style="font-size: 0.75em; font-weight: bold; margin-bottom: 4px; display: block; opacity: 0.7;">{name} • {time}</span>
            <span style="font-size: 0.95em;">{msg}</span>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def get_progress_bar_html(percentage):
    if percentage < 33: color = "#ef4444"
    elif percentage < 75: color = "#f59e0b"
    else: color = "#22c55e"
    return f"""
    <div style="width: 100%; background-color: #e2e8f0; border-radius: 6px; margin: 4px 0;">
        <div style="width: {percentage}%; background-color: {color}; padding: 3px 0; border-radius: 6px; text-align: center; color: white; font-size: 12px; font-weight: bold; min-width: 30px;">
            {percentage}%
        </div>
    </div>
    """

# --- 4. SMART DATA PERSISTENCE ---
def load_data(file, columns):
    if os.path.exists(file):
        df = pd.read_csv(file)
        for col in columns:
            if col not in df.columns:
                if col in ["Status"]: df[col] = "Active" if "User" in file else "Pending"
                elif col == "Role": df[col] = "Standard"
                elif col == "Password": df[col] = "1234" 
                elif col == "Comments": df[col] = ""
                else: df[col] = "Unknown"
        return df
    return pd.DataFrame(columns=columns)

def save_data(df, file):
    df.to_csv(file, index=False)

if "task_db" not in st.session_state: st.session_state.task_db = load_data(DB_FILE, ["Project", "Task Name", "Assignee", "Status", "Date Added", "Due Date", "Comments"])
if "subtask_db" not in st.session_state: st.session_state.subtask_db = load_data(SUBTASK_FILE, ["Project", "Parent Task", "Subtask Name", "Assignee", "Status", "Date Added", "Due Date", "Comments"])
if "user_db" not in st.session_state: st.session_state.user_db = load_data(USER_FILE, ["Full Name", "Email", "Phone Number", "Status", "Role", "Password"])
if "chat_db" not in st.session_state: st.session_state.chat_db = load_data(CHAT_FILE, ["Timestamp", "User", "Message"])
if "ai_suggestions" not in st.session_state: st.session_state.ai_suggestions = []
if "chat_ai_suggestions" not in st.session_state: st.session_state.chat_ai_suggestions = [] 

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.user_role = "Standard"
    st.session_state.is_admin = False

active_users = st.session_state.user_db[st.session_state.user_db["Status"] == "Active"] if not st.session_state.user_db.empty else pd.DataFrame()
user_list = active_users["Full Name"].tolist() if not active_users.empty else ["Unassigned"]

# ==========================================
# --- 6. MAIN APP ROUTING (LOGIN VS DASH) ---
# ==========================================

if not st.session_state.logged_in:
    st.title("🔒 Login to Badiri App")
    st.markdown("Welcome to the Marumo Technologies workspace.")
    
    with st.form("login_form"):
        st.subheader("Sign In")
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
                safe_db["Status"] = safe_db["Status"].astype(str).str.strip()

                user_match = safe_db[
                    (safe_db["Email"] == email_input.strip().lower()) & 
                    (safe_db["Password"] == pass_input.strip()) &
                    (safe_db["Status"] == "Active")
                ]
                
                if not user_match.empty:
                    real_user_idx = user_match.index[0]
                    st.session_state.logged_in = True
                    st.session_state.current_user = st.session_state.user_db.at[real_user_idx, "Full Name"]
                    st.session_state.user_role = st.session_state.user_db.at[real_user_idx, "Role"]
                    st.session_state.is_admin = (st.session_state.user_role == "Admin")
                    st.rerun()
                else:
                    st.error("❌ Invalid Email/Password, or your account is inactive.")

else:
    with st.sidebar:
        st.header("Badiri App")
        st.caption(f"Logged in as: {st.session_state.current_user}")
        st.caption(f"Role: {st.session_state.user_role}")
        
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.current_user = ""
            st.session_state.user_role = "Standard"
            st.session_state.is_admin = False
            st.rerun()
            
        st.divider()

        if st.session_state.is_admin:
            st.subheader("👤 Register New User")
            with st.form("user_form", clear_on_submit=True):
                u_name = st.text_input("Full Name")
                u_email = st.text_input("Email Address")
                u_phone = st.text_input("Phone Number")
                u_role = st.selectbox("Assign Role", ["Standard", "Admin", "Viewer Only"])
                u_pass = st.text_input("Set Initial Password", type="password")
                
                if st.form_submit_button("Register User"):
                    if u_name and u_email and u_pass:
                        new_user = pd.DataFrame([{"Full Name": u_name, "Email": u_email, "Phone Number": u_phone, "Status": "Active", "Role": u_role, "Password": u_pass}])
                        st.session_state.user_db = pd.concat([st.session_state.user_db, new_user], ignore_index=True)
                        save_data(st.session_state.user_db, USER_FILE)
                        st.success(f"✅ User '{u_name}' registered successfully!")
                        st.rerun()
                    else:
                        st.error("Name, Email, and Password are required.")

    st.title("🛠️ Project Management Dashboard")
    st.divider()

    main_col, chat_col = st.columns([3, 1], gap="large")

    with main_col:
        tabs = []
        tabs.append("🏠 My Desk")
        if st.session_state.user_role != "Viewer Only": tabs.append("📋 Project Workspace")
        tabs.append("📊 Reports & Metrics")
        if st.session_state.user_role != "Viewer Only": tabs.append("🤖 AI Assistant")
        if st.session_state.is_admin: tabs.append("🛡️ Admin Console")

        tab_list = st.tabs(tabs)
        tab_index = 0

        df = st.session_state.task_db
        sub_df_all = st.session_state.subtask_db

        # --- TAB: MY DESK ---
        with tab_list[tab_index]:
            st.subheader(f"👋 Welcome back, {st.session_state.current_user}!")
            st.markdown("Here are your active assignments. Update your progress and leave comments below.")

            my_main_tasks = df[(df["Assignee"] == st.session_state.current_user) & (df["Status"] != "Completed")]
            my_sub_tasks = sub_df_all[(sub_df_all["Assignee"] == st.session_state.current_user) & (sub_df_all["Status"] != "Completed")]

            if my_main_tasks.empty and my_sub_tasks.empty:
                st.success("🎉 You have no pending tasks! Your desk is clear.")
            else:
                if not my_main_tasks.empty:
                    st.markdown("**📌 My Main Tasks**")
                    render_table(my_main_tasks[["Project", "Task Name", "Status", "Due Date", "Comments"]])
                    
                if not my_sub_tasks.empty:
                    st.markdown("**📎 My Subtasks**")
                    render_table(my_sub_tasks[["Project", "Parent Task", "Subtask Name", "Status", "Due Date", "Comments"]], bg_color="#f8fafc")

                st.divider()
                st.markdown("#### ⚡ Inbox: Action Required")
                st.caption("Acknowledge your new assignments here. Once you change the status or leave a comment, the task will clear from this dropdown.")
                
                update_options = []
                for _, row in my_main_tasks.iterrows():
                    has_commented = st.session_state.current_user in str(row['Comments'])
                    if row['Status'] == "Pending" and not has_commented:
                        update_options.append(f"[Main] {row['Project']} - {row['Task Name']}")
                        
                for _, row in my_sub_tasks.iterrows():
                    has_commented = st.session_state.current_user in str(row['Comments'])
                    if row['Status'] == "Pending" and not has_commented:
                        update_options.append(f"[Sub] {row['Project']} - {row['Subtask Name']}")

                if len(update_options) == 0:
                    st.info("✅ Inbox Zero! You have acknowledged all your newly assigned tasks.")
                else:
                    selected_task_label = st.selectbox("Select a new task to acknowledge:", ["-- Select --"] + update_options)

                    if selected_task_label != "-- Select --":
                        is_main = selected_task_label.startswith("[Main]")
                        clean_label = selected_task_label.split("] ", 1)[1]

                        if is_main:
                            matched = my_main_tasks[my_main_tasks["Project"] + " - " + my_main_tasks["Task Name"] == clean_label]
                            real_idx = matched.index[0]
                            curr_status = df.at[real_idx, "Status"]
                            curr_comments = str(df.at[real_idx, "Comments"]) if pd.notna(df.at[real_idx, "Comments"]) else ""
                        else:
                            matched = my_sub_tasks[my_sub_tasks["Project"] + " - " + my_sub_tasks["Subtask Name"] == clean_label]
                            real_idx = matched.index[0]
                            curr_status = sub_df_all.at[real_idx, "Status"]
                            curr_comments = str(sub_df_all.at[real_idx, "Comments"]) if pd.notna(sub_df_all.at[real_idx, "Comments"]) else ""

                        with st.form("quick_update_form"):
                            new_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"], index=["Pending", "In Progress", "Completed"].index(curr_status) if curr_status in ["Pending", "In Progress", "Completed"] else 0)
                            added_comment = st.text_area("Add a new comment", placeholder="e.g., Started working on this today...")

                            if st.form_submit_button("💾 Save Update"):
                                final_comments = curr_comments
                                if added_comment.strip():
                                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                                    new_note = f"\n[{timestamp}] {st.session_state.current_user}: {added_comment.strip()}"
                                    final_comments = final_comments.strip() + new_note

                                if is_main:
                                    st.session_state.task_db.at[real_idx, "Status"] = new_status
                                    st.session_state.task_db.at[real_idx, "Comments"] = final_comments
                                    save_data(st.session_state.task_db, DB_FILE)
                                else:
                                    st.session_state.subtask_db.at[real_idx, "Status"] = new_status
                                    st.session_state.subtask_db.at[real_idx, "Comments"] = final_comments
                                    save_data(st.session_state.subtask_db, SUBTASK_FILE)

                                st.success("Task updated and cleared from Inbox!")
                                st.rerun()
        tab_index += 1

        # --- TAB: PROJECT WORKSPACE ---
        if st.session_state.user_role != "Viewer Only":
            with tab_list[tab_index]:
                st.subheader("📁 Manage Projects & Tasks")
                
                existing_projects = df["Project"].unique().tolist() if not df.empty else []
                project_selection = st.selectbox("Select a Workspace", ["-- Choose a Project --", "✨ Start a New Project"] + existing_projects)

                active_project = None
                if project_selection == "✨ Start a New Project":
                    active_project = st.text_input("Enter New Project Name", placeholder="e.g., Venue Booking")
                elif project_selection != "-- Choose a Project --":
                    active_project = project_selection

                if active_project:
                    st.divider()
                    st.markdown(f"### 📂 Project: {active_project}")
                    
                    proj_df = df[df["Project"] == active_project].drop(columns=["Due Date parsed"], errors='ignore')
                    if proj_df.empty:
                        st.info("No tasks in this project yet.")
                    else:
                        render_table(proj_df)
                        
                    st.write("") 
                    
                    with st.expander("📝 Add or Update Main Tasks", expanded=True):
                        add_col, edit_col = st.columns(2)
                        with add_col:
                            st.markdown("#### ➕ Add New Task")
                            with st.form("workspace_add_task_form", clear_on_submit=True):
                                t_name = st.text_input("Task Name")
                                t_assignee = st.selectbox("Assign To", user_list)
                                t_status = st.selectbox("Status", ["Pending", "In Progress", "Completed"])
                                t_due = st.date_input("Due Date")
                                t_comments = st.text_area("Comments", placeholder="Add instructions or notes...")
                                
                                if st.form_submit_button("Add to Project"):
                                    if t_name:
                                        new_task = pd.DataFrame([{"Project": active_project, "Task Name": t_name, "Assignee": t_assignee, "Status": t_status, "Date Added": datetime.now().strftime("%Y-%m-%d"), "Due Date": str(t_due), "Comments": t_comments}])
                                        st.session_state.task_db = pd.concat([st.session_state.task_db, new_task], ignore_index=True)
                                        save_data(st.session_state.task_db, DB_FILE)
                                        st.success("Task added!")
                                        st.rerun()
                        with edit_col:
                            st.markdown("#### 🚀 Update or Forward Task")
                            if proj_df.empty:
                                st.caption("Add a task to enable editing.")
                            else:
                                task_dict = {idx: row["Task Name"] for idx, row in proj_df.iterrows()}
                                selected_idx = st.selectbox("Select Task", options=list(task_dict.keys()), format_func=lambda x: task_dict[x])
                                if selected_idx is not None:
                                    current_assignee = df.at[selected_idx, "Assignee"]
                                    current_status = df.at[selected_idx, "Status"]
                                    current_comments = str(df.at[selected_idx, "Comments"]) if pd.notna(df.at[selected_idx, "Comments"]) else ""
                                    with st.form("workspace_update_form"):
                                        assignee_index = user_list.index(current_assignee) if current_assignee in user_list else 0
                                        new_assignee = st.selectbox("Forward / Reassign To", user_list, index=assignee_index)
                                        new_status = st.selectbox("Update Status", ["Pending", "In Progress", "Completed"], index=["Pending", "In Progress", "Completed"].index(current_status) if current_status in ["Pending", "In Progress", "Completed"] else 0)
                                        new_comments = st.text_area("Update Comments", value=current_comments, height=100)
                                        if st.form_submit_button("💾 Save Updates"):
                                            if new_assignee != current_assignee:
                                                forward_note = f"\n[System: Forwarded from {current_assignee} to {new_assignee} on {datetime.now().strftime('%Y-%m-%d %H:%M')}]"
                                                new_comments = new_comments.strip() + forward_note
                                            st.session_state.task_db.at[selected_idx, "Assignee"] = new_assignee
                                            st.session_state.task_db.at[selected_idx, "Status"] = new_status
                                            st.session_state.task_db.at[selected_idx, "Comments"] = new_comments
                                            save_data(st.session_state.task_db, DB_FILE)
                                            st.success("Task updated!")
                                            st.rerun()

                    with st.expander("🗂️ Manage Subtasks", expanded=False):
                        st.markdown('<div style="background-color: #f1f5f9; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 5px solid #64748b;"><h4 style="margin:0; color: #334155;">🗂️ Subtask Workspace</h4></div>', unsafe_allow_html=True)
                        if proj_df.empty:
                            st.info("You need to add a Main Task above before you can attach Subtasks to it.")
                        else:
                            parent_task = st.selectbox("Select Main Task to view/add Subtasks:", ["-- Select --"] + proj_df["Task Name"].tolist())
                            if parent_task != "-- Select --":
                                active_subtasks = sub_df_all[(sub_df_all["Project"] == active_project) & (sub_df_all["Parent Task"] == parent_task)]
                                if not active_subtasks.empty:
                                    render_table(active_subtasks.drop(columns=["Project", "Parent Task"], errors="ignore"), bg_color="#f8fafc")
                                st.write("")
                                s_add_col, s_edit_col = st.columns(2)
                                with s_add_col:
                                    st.markdown("#### ➕ Add Subtask")
                                    with st.form("add_sub_form", clear_on_submit=True):
                                        s_name = st.text_input("Subtask Name")
                                        s_assignee = st.selectbox("Assign Subtask To", user_list)
                                        s_due = st.date_input("Due Date")
                                        if st.form_submit_button("Create Subtask") and s_name:
                                            new_sub = pd.DataFrame([{"Project": active_project, "Parent Task": parent_task, "Subtask Name": s_name, "Assignee": s_assignee, "Status": "Pending", "Date Added": datetime.now().strftime("%Y-%m-%d"), "Due Date": str(s_due), "Comments": ""}])
                                            st.session_state.subtask_db = pd.concat([st.session_state.subtask_db, new_sub], ignore_index=True)
                                            save_data(st.session_state.subtask_db, SUBTASK_FILE)
                                            st.success("Subtask added!")
                                            st.rerun()
                                with s_edit_col:
                                    st.markdown("#### 🚀 Update Subtask")
                                    if not active_subtasks.empty:
                                        sub_dict = {idx: row["Subtask Name"] for idx, row in active_subtasks.iterrows()}
                                        sub_idx = st.selectbox("Select Subtask", options=list(sub_dict.keys()), format_func=lambda x: sub_dict[x])
                                        if sub_idx is not None:
                                            with st.form("update_sub_form"):
                                                new_s_status = st.selectbox("Update Status", ["Pending", "In Progress", "Completed"])
                                                if st.form_submit_button("💾 Save Subtask"):
                                                    st.session_state.subtask_db.at[sub_idx, "Status"] = new_s_status
                                                    save_data(st.session_state.subtask_db, SUBTASK_FILE)
                                                    st.success("Subtask updated!")
                                                    st.rerun()
            tab_index += 1

        # --- TAB: REPORTS & METRICS ---
        with tab_list[tab_index]:
            if df.empty:
                st.info("No tasks to report on.")
            else:
                df['Due Date parsed'] = pd.to_datetime(df['Due Date'], errors='coerce')
                today_ts = pd.Timestamp.now().normalize()
                overdue_df = df[(df["Due Date parsed"] < today_ts) & (df["Status"] != "Completed")]
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Main Tasks", len(df))
                c2.metric("✅ Tasks Completed", len(df[df["Status"] == "Completed"]))
                c3.metric("Total Subtasks", len(sub_df_all))
                c4.metric("🚨 Overdue Tasks", len(overdue_df))
                
                st.divider()
                st.subheader("📊 Project Health Dashboard")
                project_health_html = '<div style="background-color: white; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0;">'
                for proj in df["Project"].unique():
                    p_df = df[df["Project"] == proj]
                    p_total = len(p_df)
                    p_completed = len(p_df[p_df["Status"] == "Completed"])
                    p_pct = int((p_completed / p_total) * 100) if p_total > 0 else 0
                    
                    project_health_html += f"<div><strong>{proj}</strong> ({p_completed}/{p_total} Tasks Completed)</div>"
                    project_health_html += get_progress_bar_html(p_pct)
                    project_health_html += "<br>"
                project_health_html += '</div>'
                st.markdown(project_health_html, unsafe_allow_html=True)
                
                st.divider()
                st.subheader("🚨 Bottleneck & Overdue Report")
                if overdue_df.empty:
                    st.success("Excellent! No tasks are currently overdue.")
                else:
                    st.error(f"Attention: {len(overdue_df)} task(s) have passed their due date!")
                    overdue_display = overdue_df.copy()
                    overdue_display['Days Overdue'] = (today_ts - overdue_display['Due Date parsed']).dt.days
                    overdue_display['Days Overdue'] = overdue_display['Days Overdue'].apply(lambda x: f"⚠️ {int(x)} days")
                    
                    clean_overdue = overdue_display[["Project", "Task Name", "Assignee", "Days Overdue"]]
                    render_table(clean_overdue, bg_color="#fee2e2")

                st.divider()
                st.subheader("📈 Team Performance & Capacity Matrix")
                
                all_assignments = []
                for _, row in df.iterrows():
                    all_assignments.append({"Assignee": row["Assignee"], "Status": row["Status"]})
                for _, row in sub_df_all.iterrows():
                    all_assignments.append({"Assignee": row["Assignee"], "Status": row["Status"]})
                
                perf_df = pd.DataFrame(all_assignments)
                
                if not perf_df.empty:
                    matrix_html = '<table style="width:100%; border-collapse: collapse; text-align: left; font-family: sans-serif;">'
                    matrix_html += '<tr style="background-color: #f1f5f9; border-bottom: 2px solid #cbd5e1;">'
                    matrix_html += '<th style="padding: 10px;">Team Member</th>'
                    matrix_html += '<th style="padding: 10px;">Total Load</th>'
                    matrix_html += '<th style="padding: 10px;">Completed</th>'
                    matrix_html += '<th style="padding: 10px;">Efficiency Rate</th></tr>'
                    
                    for user in perf_df["Assignee"].unique():
                        u_tasks = perf_df[perf_df["Assignee"] == user]
                        u_total = len(u_tasks)
                        u_comp = len(u_tasks[u_tasks["Status"] == "Completed"])
                        u_pct = int((u_comp / u_total) * 100) if u_total > 0 else 0
                        
                        matrix_html += '<tr style="border-bottom: 1px solid #e2e8f0;">'
                        matrix_html += f'<td style="padding: 10px;"><strong>{user}</strong></td>'
                        matrix_html += f'<td style="padding: 10px;">{u_total}</td>'
                        matrix_html += f'<td style="padding: 10px;">{u_comp}</td>'
                        matrix_html += f'<td style="padding: 10px; width: 40%;">{get_progress_bar_html(u_pct)}</td></tr>'
                        
                    matrix_html += '</table>'
                    st.markdown(f'<div style="background-color: white; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0;">{matrix_html}</div>', unsafe_allow_html=True)
                
                st.divider()
                st.subheader("📥 Export Center")
                export_col1, export_col2 = st.columns(2)
                
                with export_col1:
                    if HAS_PPTX:
                        ppt_file = create_ppt(df, sub_df_all)
                        st.download_button("📊 Download Comprehensive PowerPoint Deck", data=ppt_file, file_name=f"Badiri_Report_{datetime.now().strftime('%Y%m%d')}.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation", type="primary")
                    else:
                        st.warning("⚠️ Run `pip install python-pptx` to enable PowerPoint.")
                        
                with export_col2:
                    csv_data = df.to_csv(index=False).encode('utf-8')
                    st.download_button("📈 Download Raw Data (Excel/CSV)", data=csv_data, file_name=f"Badiri_Data_Export_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
                    
        tab_index += 1

        # --- TAB: AI ASSISTANT ---
        if st.session_state.user_role != "Viewer Only":
            with tab_list[tab_index]:
                st.markdown("## 🤖 Gemini AI Task Extractor")
                gemini_key = st.text_input("🔑 Enter your Google Gemini API Key:", type="password", help="Get a free key at aistudio.google.com")
                st.divider()

                # --- OPTION 1: DOCUMENT SCANNER ---
                st.subheader("📷 Option 1: Scan Meeting Minutes")
                st.markdown("Upload a photo of your handwritten or typed meeting minutes.")
                scanned_file = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])
                
                if st.button("🔍 Analyze Image"):
                    if not gemini_key:
                        st.error("Please enter your Gemini API Key above.")
                    elif not scanned_file:
                        st.error("Please upload an image of the minutes.")
                    else:
                        with st.spinner("Gemini AI is reading your document... Please wait."):
                            try:
                                img_bytes = scanned_file.read()
                                base64_img = base64.b64encode(img_bytes).decode('utf-8')
                                mime_type = "image/jpeg" if scanned_file.name.lower().endswith(('jpg', 'jpeg')) else "image/png"
                                
                                prompt_text = f"""
                                You are a professional project manager. Read the attached image of meeting minutes.
                                Extract ONLY actionable items.
                                Return your response strictly as a JSON list of objects.
                                Each object must have exactly these keys: 
                                'Project' (infer a short project name from context), 
                                'Task Name' (the action item), 
                                'Assignee' (match the name to this list if possible: {user_list}, otherwise output 'Unassigned').
                                Do not add any markdown formatting or explanations. Just the JSON array.
                                """
                                
                                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                                payload = {"contents": [{"parts": [{"text": prompt_text}, {"inline_data": {"mime_type": mime_type, "data": base64_img}}]}]}
                                
                                response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
                                response_data = response.json()
                                
                                if response.status_code == 200 and 'candidates' in response_data:
                                    raw_text = response_data['candidates'][0]['content']['parts'][0]['text']
                                    clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                                    try:
                                        st.session_state.ai_suggestions = json.loads(clean_text)
                                        st.success("Successfully analyzed image!")
                                    except json.JSONDecodeError:
                                        st.error(f"AI returned invalid format. Raw output: {raw_text}")
                                else:
                                    err_msg = response_data.get('error', {}).get('message', str(response_data))
                                    st.error(f"Google API Error: {err_msg}")
                            except Exception as e:
                                st.error(f"Failed to process image: {str(e)}")
                                
                if st.session_state.ai_suggestions:
                    st.markdown("#### ✨ Suggested Tasks from Image")
                    
                    if st.session_state.is_admin:
                        with st.form("img_approval_form"):
                            st.write("**Select the tasks you want to import:**")
                            
                            # Clean Header Row
                            hc1, hc2, hc3, hc4 = st.columns([0.5, 2, 4, 2])
                            hc1.write("✔")
                            hc2.write("**Project**")
                            hc3.write("**Task Name**")
                            hc4.write("**Assignee**")
                            st.markdown("<hr style='margin: 0px;'/>", unsafe_allow_html=True)
                            
                            selections = []
                            for idx, item in enumerate(st.session_state.ai_suggestions):
                                c1, c2, c3, c4 = st.columns([0.5, 2, 4, 2])
                                # Checked by default!
                                sel = c1.checkbox("", value=True, key=f"img_chk_{idx}")
                                selections.append(sel)
                                c2.write(item.get("Project", "N/A"))
                                c3.write(item.get("Task Name", "N/A"))
                                c4.write(item.get("Assignee", "Unassigned"))
                            
                            st.write("")
                            if st.form_submit_button("✅ Admin: Approve Selected Tasks"):
                                added = 0
                                for idx, is_selected in enumerate(selections):
                                    if is_selected:
                                        item = st.session_state.ai_suggestions[idx]
                                        new_task = pd.DataFrame([{
                                            "Project": item.get("Project", "AI Extracted"), 
                                            "Task Name": item.get("Task Name", "Unnamed Task"), 
                                            "Assignee": item.get("Assignee", "Unassigned"), 
                                            "Status": "Pending", 
                                            "Date Added": datetime.now().strftime("%Y-%m-%d"), 
                                            "Due Date": datetime.now().strftime("%Y-%m-%d"), 
                                            "Comments": "Auto-extracted from minutes by Gemini AI."
                                        }])
                                        st.session_state.task_db = pd.concat([st.session_state.task_db, new_task], ignore_index=True)
                                        added += 1
                                
                                if added > 0:
                                    save_data(st.session_state.task_db, DB_FILE)
                                    st.session_state.ai_suggestions = []
                                    st.success(f"{added} tasks imported! Go to Workspace to view them.")
                                    st.rerun()
                                else:
                                    st.warning("No tasks were selected. Try again.")
                    else:
                        render_table(pd.DataFrame(st.session_state.ai_suggestions), bg_color="#e0f2fe")
                        st.info("🔒 Only an Admin can approve and import these tasks.")

                st.divider()

                # --- OPTION 2: CHAT MINER ---
                st.subheader("💬 Option 2: Extract Tasks from Team Chat")
                st.markdown("Let the AI read the recent Team Chat and pull out actionable promises made by team members.")
                
                if st.button("🧠 Analyze Recent Chat"):
                    if not gemini_key:
                        st.error("Please enter your Gemini API Key at the top.")
                    elif st.session_state.chat_db.empty:
                        st.warning("The Team Chat is currently empty.")
                    else:
                        with st.spinner("Gemini is reading the chat logs..."):
                            try:
                                chat_transcript = ""
                                for _, row in st.session_state.chat_db.tail(50).iterrows():
                                    chat_transcript += f"[{row['Timestamp']}] {row['User']}: {row['Message']}\n"

                                chat_prompt = f"""
                                You are a project manager. Read the following team chat transcript.
                                Identify any actionable tasks that team members agreed to do.
                                Return a JSON list of objects with exactly these keys: 
                                'Project' (infer a short project name from context, or use 'Team Chat'), 
                                'Task Name' (the action item), 
                                'Assignee' (match the name to this list if possible: {user_list}, otherwise output 'Unassigned').
                                Do not add any markdown formatting or explanations. Just the JSON array.
                                If no tasks are found, return an empty array: [].
                                
                                CHAT TRANSCRIPT:
                                {chat_transcript}
                                """

                                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                                payload = {"contents": [{"parts": [{"text": chat_prompt}]}]}
                                
                                response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
                                response_data = response.json()
                                
                                if response.status_code == 200 and 'candidates' in response_data:
                                    raw_text = response_data['candidates'][0]['content']['parts'][0]['text']
                                    clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                                    try:
                                        extracted_data = json.loads(clean_text)
                                        st.session_state.chat_ai_suggestions = extracted_data
                                        if len(extracted_data) == 0:
                                            st.info("No clear action items found in the recent chat.")
                                        else:
                                            st.success(f"Found {len(extracted_data)} potential tasks in the chat!")
                                    except json.JSONDecodeError:
                                        st.error(f"AI returned invalid format. Raw output: {raw_text}")
                                else:
                                    err_msg = response_data.get('error', {}).get('message', str(response_data))
                                    st.error(f"Google API Error: {err_msg}")
                            except Exception as e:
                                st.error(f"Failed to process chat: {str(e)}")

                if st.session_state.chat_ai_suggestions:
                    st.markdown("#### ✨ Suggested Tasks from Chat")
                    
                    if st.session_state.is_admin:
                        with st.form("chat_approval_form"):
                            st.write("**Select the tasks you want to import:**")
                            
                            hc1, hc2, hc3, hc4 = st.columns([0.5, 2, 4, 2])
                            hc1.write("✔")
                            hc2.write("**Project**")
                            hc3.write("**Task Name**")
                            hc4.write("**Assignee**")
                            st.markdown("<hr style='margin: 0px;'/>", unsafe_allow_html=True)
                            
                            selections = []
                            for idx, item in enumerate(st.session_state.chat_ai_suggestions):
                                c1, c2, c3, c4 = st.columns([0.5, 2, 4, 2])
                                sel = c1.checkbox("", value=True, key=f"chat_chk_{idx}")
                                selections.append(sel)
                                c2.write(item.get("Project", "N/A"))
                                c3.write(item.get("Task Name", "N/A"))
                                c4.write(item.get("Assignee", "Unassigned"))
                            
                            st.write("")
                            if st.form_submit_button("✅ Admin: Approve Selected Tasks"):
                                added = 0
                                for idx, is_selected in enumerate(selections):
                                    if is_selected:
                                        item = st.session_state.chat_ai_suggestions[idx]
                                        new_task = pd.DataFrame([{
                                            "Project": item.get("Project", "Chat Extraction"), 
                                            "Task Name": item.get("Task Name", "Unnamed Task"), 
                                            "Assignee": item.get("Assignee", "Unassigned"), 
                                            "Status": "Pending", 
                                            "Date Added": datetime.now().strftime("%Y-%m-%d"), 
                                            "Due Date": datetime.now().strftime("%Y-%m-%d"), 
                                            "Comments": "Auto-extracted from Team Chat by Gemini AI."
                                        }])
                                        st.session_state.task_db = pd.concat([st.session_state.task_db, new_task], ignore_index=True)
                                        added += 1
                                
                                if added > 0:
                                    save_data(st.session_state.task_db, DB_FILE)
                                    st.session_state.chat_ai_suggestions = []
                                    st.success(f"{added} tasks safely imported! Go to Workspace to view them.")
                                    st.rerun()
                                else:
                                    st.warning("No tasks were selected. Try again.")
                    else:
                        render_table(pd.DataFrame(st.session_state.chat_ai_suggestions), bg_color="#fce7f3") 
                        st.info("🔒 Only an Admin can approve and import tasks extracted from the chat.")
            tab_index += 1

        # --- TAB: ADMIN CONSOLE ---
        if st.session_state.is_admin:
            with tab_list[tab_index]:
                st.subheader("User Management Console")
                if st.session_state.user_db.empty:
                    st.info("No users registered.")
                else:
                    st.markdown("**Registered Team Members (Full Details):**")
                    render_table(st.session_state.user_db)
                    
                    st.divider()
                    st.write("**📝 Edit Existing User Details**")
                    
                    user_to_update = st.selectbox("Select User Profile to Edit", ["-- Select User --"] + st.session_state.user_db["Full Name"].tolist())
                    
                    if user_to_update != "-- Select User --":
                        curr_user_row = st.session_state.user_db[st.session_state.user_db["Full Name"] == user_to_update].iloc[0]
                        curr_idx = st.session_state.user_db.index[st.session_state.user_db["Full Name"] == user_to_update].tolist()[0]
                        
                        with st.form("update_user_details_form"):
                            c1, c2 = st.columns(2)
                            new_u_name = c1.text_input("Full Name", value=curr_user_row["Full Name"])
                            new_u_email = c2.text_input("Email Address", value=curr_user_row["Email"])
                            new_u_phone = c1.text_input("Phone Number", value=str(curr_user_row["Phone Number"]).replace('nan',''))
                            
                            status_opts = ["Active", "Suspended", "Blocked"]
                            new_u_status = c2.selectbox("Status", status_opts, index=status_opts.index(curr_user_row["Status"]) if curr_user_row["Status"] in status_opts else 0)
                            
                            role_opts = ["Standard", "Admin", "Viewer Only"]
                            new_u_role = c1.selectbox("Role", role_opts, index=role_opts.index(curr_user_row["Role"]) if curr_user_row["Role"] in role_opts else 0)
                            
                            new_u_pass = c2.text_input("Password", value=curr_user_row["Password"], type="password")
                            
                            if st.form_submit_button("💾 Save Profile Changes"):
                                if new_u_name and new_u_email and new_u_pass:
                                    st.session_state.user_db.at[curr_idx, 'Full Name'] = new_u_name
                                    st.session_state.user_db.at[curr_idx, 'Email'] = new_u_email
                                    st.session_state.user_db.at[curr_idx, 'Phone Number'] = new_u_phone
                                    st.session_state.user_db.at[curr_idx, 'Status'] = new_u_status
                                    st.session_state.user_db.at[curr_idx, 'Role'] = new_u_role
                                    st.session_state.user_db.at[curr_idx, 'Password'] = new_u_pass
                                    save_data(st.session_state.user_db, USER_FILE)
                                    
                                    if new_u_name != user_to_update:
                                        st.session_state.task_db.loc[st.session_state.task_db['Assignee'] == user_to_update, 'Assignee'] = new_u_name
                                        save_data(st.session_state.task_db, DB_FILE)
                                        
                                        st.session_state.subtask_db.loc[st.session_state.subtask_db['Assignee'] == user_to_update, 'Assignee'] = new_u_name
                                        save_data(st.session_state.subtask_db, SUBTASK_FILE)

                                    st.success(f"Profile for {new_u_name} updated successfully!")
                                    st.rerun()
                                else:
                                    st.error("Name, Email, and Password cannot be empty.")

    # ==========================================
    # RIGHT SIDE: THE GLOBAL TEAM CHAT
    # ==========================================
    with chat_col:
        st.markdown('<div style="background-color: #f8fafc; padding: 10px; border-radius: 8px; border-top: 4px solid #3b82f6;"><h3 style="margin:0; color: #1e293b; text-align: center;">💬 Team Chat</h3></div>', unsafe_allow_html=True)
        st.write("") 
        
        st.session_state.chat_db = load_data(CHAT_FILE, ["Timestamp", "User", "Message"])
        
        if st.session_state.chat_db.empty:
            st.caption("No messages yet. Say hello!")
        else:
            recent_chats = st.session_state.chat_db.tail(20)
            for _, msg_row in recent_chats.iterrows():
                is_me = (msg_row["User"] == st.session_state.current_user)
                render_chat_bubble(msg_row["User"], msg_row["Message"], msg_row["Timestamp"], is_me)
                
        st.divider()
        
        with st.form("chat_input_form", clear_on_submit=True):
            new_msg = st.text_input("Type your message...", placeholder="e.g. I will book the venue tomorrow.")
            
            c1, c2 = st.columns([1, 1])
            with c1:
                submitted = st.form_submit_button("📨 Send")
            with c2:
                refresh = st.form_submit_button("🔄 Refresh")
                
            if submitted and new_msg:
                new_chat_row = pd.DataFrame([{
                    "Timestamp": datetime.now().strftime("%d %b %H:%M"), 
                    "User": st.session_state.current_user, 
                    "Message": new_msg
                }])
                st.session_state.chat_db = pd.concat([st.session_state.chat_db, new_chat_row], ignore_index=True)
                save_data(st.session_state.chat_db, CHAT_FILE)
                st.rerun()
                
            if refresh:
                st.rerun() 

# --- END OF FILE ---