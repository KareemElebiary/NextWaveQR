"""
Graphical User Interface for IEEE Event QR Pass Generator & Email Sender
========================================================================
Tab 1: Generate QR passes & badges from attendee CSV (Name, Phone, IEEE Member)
Tab 2: Dispatch personalized passes by email with anti-spam protections & Kareem's signature
"""

import os
import sys
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd

from qr_generator import (
    detect_columns,
    parse_ieee_status,
    process_attendees,
    create_sample_csv
)
from email_sender import (
    batch_send_passes,
    load_env_credentials
)

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class IEEEEventApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IEEE Event Pass Generator & Email Dispatcher")
        self.geometry("860x740")
        self.minsize(760, 640)
        self.configure(bg="#F1F5F9")

        # Generator Variables
        self.csv_path_var = tk.StringVar(value="")
        self.output_dir_var = tk.StringVar(value="output_qrs")
        self.format_var = tk.StringVar(value="json")
        self.generate_badges_var = tk.BooleanVar(value=True)
        self.gen_status_var = tk.StringVar(value="Ready. Select an attendee CSV file to begin.")

        # Email Dispatcher Variables (load from .env if present)
        env_cfg = load_env_credentials()
        self.sender_email_var = tk.StringVar(value=env_cfg.get("sender_email", ""))
        self.sender_pwd_var = tk.StringVar(value=env_cfg.get("sender_password", ""))
        self.smtp_host_var = tk.StringVar(value=env_cfg.get("smtp_host", "smtp.gmail.com"))
        self.smtp_port_var = tk.IntVar(value=env_cfg.get("smtp_port", 587))
        self.event_name_var = tk.StringVar(value=env_cfg.get("event_name", "Next Wave II"))
        self.sender_name_var = tk.StringVar(value=env_cfg.get("sender_name", "Kareem Elebairy | IEEE Computer Society"))
        self.delay_var = tk.DoubleVar(value=2.5)
        self.test_email_var = tk.StringVar(value=env_cfg.get("sender_email", ""))
        self.skip_sent_var = tk.BooleanVar(value=True)
        self.show_pwd_var = tk.BooleanVar(value=False)

        # Auto-mirror sender email to test email if test email is empty
        def on_sender_change(*args):
            cur_test = self.test_email_var.get().strip()
            cur_sender = self.sender_email_var.get().strip()
            if not cur_test or "@" not in cur_test:
                self.test_email_var.set(cur_sender)

        self.sender_email_var.trace_add("write", on_sender_change)

        self._apply_styles()
        self._build_ui()

        # Auto-detect default CSV file
        for candidate in ["Next Wave II - Form Responses 1.csv", "sample_attendees.csv"]:
            if os.path.exists(candidate):
                self.csv_path_var.set(os.path.abspath(candidate))
                self.load_csv_preview(self.csv_path_var.get())
                break

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Global treeview
        style.configure(
            "Treeview",
            background="#FFFFFF",
            foreground="#1E293B",
            rowheight=26,
            fieldbackground="#FFFFFF",
            font=("Segoe UI", 9)
        )
        style.configure(
            "Treeview.Heading",
            background="#E2E8F0",
            foreground="#0F172A",
            font=("Segoe UI", 9, "bold")
        )
        style.map("Treeview", background=[("selected", "#00629B")], foreground=[("selected", "#FFFFFF")])

        # Notebook tabs
        style.configure(
            "TNotebook.Tab",
            font=("Segoe UI", 10, "bold"),
            padding=[16, 8],
            background="#E2E8F0",
            foreground="#475569"
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#FFFFFF")],
            foreground=[("selected", "#00629B")]
        )

    def _build_ui(self):
        # 1. Header Banner
        header = tk.Frame(self, bg="#0B192C", height=70)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="Next Wave II - Event Pass Generator & Mail Dispatcher",
            font=("Segoe UI", 15, "bold"),
            fg="#FFFFFF",
            bg="#0B192C"
        )
        title.pack(anchor="w", padx=25, pady=(10, 2))

        subtitle = tk.Label(
            header,
            text="IEEE Computer Society • Attendance Passes & Anti-Spam Email Sender",
            font=("Segoe UI", 9),
            fg="#94A3B8",
            bg="#0B192C"
        )
        subtitle.pack(anchor="w", padx=25)

        # 2. Notebook (Tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=10)

        # Tab 1: QR Generator
        self.tab_generator = tk.Frame(self.notebook, bg="#F1F5F9", padx=15, pady=10)
        self.notebook.add(self.tab_generator, text="  🎫 1. Generate QR Passes  ")
        self._build_generator_tab()

        # Tab 2: Email Sender
        self.tab_mailer = tk.Frame(self.notebook, bg="#F1F5F9", padx=15, pady=10)
        self.notebook.add(self.tab_mailer, text="  ✉️ 2. Send Passes by Email  ")
        self._build_mailer_tab()

    # ==========================================================================
    # Tab 1: QR Code & Badge Generator
    # ==========================================================================
    def _build_generator_tab(self):
        # File selector card
        card_file = tk.LabelFrame(
            self.tab_generator,
            text=" 1. Attendee CSV File ",
            font=("Segoe UI", 10, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            padx=12,
            pady=10,
            relief="solid",
            bd=1
        )
        card_file.pack(fill="x", pady=(0, 8))

        row_f = tk.Frame(card_file, bg="#FFFFFF")
        row_f.pack(fill="x")

        entry_csv = tk.Entry(
            row_f,
            textvariable=self.csv_path_var,
            font=("Segoe UI", 9),
            bg="#F8FAFC",
            relief="solid",
            bd=1
        )
        entry_csv.pack(side="left", fill="x", expand=True, ipady=3, padx=(0, 8))

        btn_browse = tk.Button(
            row_f,
            text="Browse...",
            command=self.browse_csv,
            font=("Segoe UI", 9, "bold"),
            bg="#E2E8F0",
            fg="#0F172A",
            relief="flat",
            padx=10,
            pady=3,
            cursor="hand2"
        )
        btn_browse.pack(side="left", padx=(0, 6))

        btn_sample = tk.Button(
            row_f,
            text="Sample CSV",
            command=self.create_sample,
            font=("Segoe UI", 9),
            bg="#F1F5F9",
            fg="#475569",
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2"
        )
        btn_sample.pack(side="left")

        # Preview table
        card_preview = tk.LabelFrame(
            self.tab_generator,
            text=" 2. Attendees Preview ",
            font=("Segoe UI", 10, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            padx=8,
            pady=8,
            relief="solid",
            bd=1
        )
        card_preview.pack(fill="both", expand=True, pady=(0, 8))

        self.tree = ttk.Treeview(
            card_preview,
            columns=("PassID", "Name", "Number", "IEEE_Status", "Email"),
            show="headings",
            selectmode="browse"
        )
        self.tree.heading("PassID", text="Pass ID")
        self.tree.heading("Name", text="Attendee Name")
        self.tree.heading("Number", text="Phone Number")
        self.tree.heading("IEEE_Status", text="IEEE Member?")
        self.tree.heading("Email", text="Email Address")

        self.tree.column("PassID", width=65, anchor="center")
        self.tree.column("Name", width=200, anchor="w")
        self.tree.column("Number", width=120, anchor="center")
        self.tree.column("IEEE_Status", width=100, anchor="center")
        self.tree.column("Email", width=220, anchor="w")

        tree_scroll_y = ttk.Scrollbar(card_preview, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")

        # Options Card
        card_opt = tk.LabelFrame(
            self.tab_generator,
            text=" 3. Generation Options ",
            font=("Segoe UI", 10, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            padx=12,
            pady=8,
            relief="solid",
            bd=1
        )
        card_opt.pack(fill="x", pady=(0, 8))

        row_o = tk.Frame(card_opt, bg="#FFFFFF")
        row_o.pack(fill="x")

        chk_badge = tk.Checkbutton(
            row_o,
            text="Generate Visual Event Pass Badges (phone number hidden, numeric Pass ID)",
            variable=self.generate_badges_var,
            font=("Segoe UI", 9),
            bg="#FFFFFF"
        )
        chk_badge.pack(side="left")

        lbl_out = tk.Label(row_o, text="Output Folder:", font=("Segoe UI", 9), bg="#FFFFFF", fg="#334155")
        lbl_out.pack(side="left", padx=(25, 6))

        entry_out = tk.Entry(
            row_o,
            textvariable=self.output_dir_var,
            font=("Segoe UI", 9),
            bg="#F8FAFC",
            relief="solid",
            bd=1,
            width=20
        )
        entry_out.pack(side="left")

        # Action Buttons
        act_frame = tk.Frame(self.tab_generator, bg="#F1F5F9")
        act_frame.pack(fill="x", pady=2)

        self.btn_generate = tk.Button(
            act_frame,
            text="Generate All Passes & QR Codes",
            command=self.start_generation,
            font=("Segoe UI", 10, "bold"),
            bg="#00629B",
            fg="#FFFFFF",
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2"
        )
        self.btn_generate.pack(side="left", padx=(0, 8))

        btn_open = tk.Button(
            act_frame,
            text="Open Output Folder",
            command=self.open_output_folder,
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg="#1E293B",
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2"
        )
        btn_open.pack(side="left")

        self.gen_prog = ttk.Progressbar(act_frame, orient="horizontal", mode="indeterminate")
        self.gen_prog.pack(side="right", fill="x", expand=True, padx=(12, 0))

        # Generator Status label
        lbl_st = tk.Label(
            self.tab_generator,
            textvariable=self.gen_status_var,
            font=("Segoe UI", 9),
            fg="#475569",
            bg="#F1F5F9",
            anchor="w"
        )
        lbl_st.pack(fill="x", pady=(4, 0))

    # ==========================================================================
    # Tab 2: Email Sender (Anti-Spam Optimized)
    # ==========================================================================
    def _build_mailer_tab(self):
        # 1. Credentials Card
        card_cred = tk.LabelFrame(
            self.tab_mailer,
            text=" 1. Sender SMTP Credentials ",
            font=("Segoe UI", 10, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            padx=15,
            pady=10,
            relief="solid",
            bd=1
        )
        card_cred.pack(fill="x", pady=(0, 8))

        row_c1 = tk.Frame(card_cred, bg="#FFFFFF")
        row_c1.pack(fill="x", pady=2)

        tk.Label(row_c1, text="Sender Email:", width=14, anchor="w", font=("Segoe UI", 9), bg="#FFFFFF").pack(side="left")
        entry_email = tk.Entry(row_c1, textvariable=self.sender_email_var, font=("Segoe UI", 9), bg="#F8FAFC", relief="solid", bd=1, width=32)
        entry_email.pack(side="left", padx=(0, 20))

        tk.Label(row_c1, text="App Password:", width=14, anchor="w", font=("Segoe UI", 9), bg="#FFFFFF").pack(side="left")
        self.entry_pwd = tk.Entry(row_c1, textvariable=self.sender_pwd_var, font=("Segoe UI", 9), bg="#F8FAFC", relief="solid", bd=1, width=22, show="*")
        self.entry_pwd.pack(side="left", padx=(0, 8))

        chk_show = tk.Checkbutton(row_c1, text="Show", variable=self.show_pwd_var, command=self.toggle_pwd_visibility, font=("Segoe UI", 8), bg="#FFFFFF")
        chk_show.pack(side="left")

        row_c2 = tk.Frame(card_cred, bg="#FFFFFF")
        row_c2.pack(fill="x", pady=(6, 2))

        tk.Label(row_c2, text="SMTP Host:", width=14, anchor="w", font=("Segoe UI", 9), bg="#FFFFFF").pack(side="left")
        tk.Entry(row_c2, textvariable=self.smtp_host_var, font=("Segoe UI", 9), bg="#F8FAFC", relief="solid", bd=1, width=20).pack(side="left", padx=(0, 20))

        tk.Label(row_c2, text="SMTP Port:", width=10, anchor="w", font=("Segoe UI", 9), bg="#FFFFFF").pack(side="left")
        tk.Entry(row_c2, textvariable=self.smtp_port_var, font=("Segoe UI", 9), bg="#F8FAFC", relief="solid", bd=1, width=8).pack(side="left", padx=(0, 20))

        tk.Label(row_c2, text="Delay (seconds):", font=("Segoe UI", 9), bg="#FFFFFF").pack(side="left", padx=(0, 4))
        tk.Entry(row_c2, textvariable=self.delay_var, font=("Segoe UI", 9), bg="#F8FAFC", relief="solid", bd=1, width=6).pack(side="left")

        # Help tooltip
        lbl_hint = tk.Label(
            card_cred,
            text="💡 Gmail Tip: Use a 16-character App Password (Google Account -> Security -> 2-Step Verification -> App Passwords).",
            font=("Segoe UI", 8, "italic"),
            fg="#0284C7",
            bg="#FFFFFF"
        )
        lbl_hint.pack(anchor="w", pady=(6, 0))

        # 2. Email Signature & Event Info Card
        card_info = tk.LabelFrame(
            self.tab_mailer,
            text=" 2. Event & Signature Settings ",
            font=("Segoe UI", 10, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            padx=15,
            pady=10,
            relief="solid",
            bd=1
        )
        card_info.pack(fill="x", pady=(0, 8))

        row_i1 = tk.Frame(card_info, bg="#FFFFFF")
        row_i1.pack(fill="x", pady=2)

        tk.Label(row_i1, text="Event Name:", width=14, anchor="w", font=("Segoe UI", 9), bg="#FFFFFF").pack(side="left")
        tk.Entry(row_i1, textvariable=self.event_name_var, font=("Segoe UI", 9), bg="#F8FAFC", relief="solid", bd=1, width=28).pack(side="left", padx=(0, 20))

        tk.Label(row_i1, text="From Name:", width=12, anchor="w", font=("Segoe UI", 9), bg="#FFFFFF").pack(side="left")
        tk.Entry(row_i1, textvariable=self.sender_name_var, font=("Segoe UI", 9), bg="#F8FAFC", relief="solid", bd=1, width=38).pack(side="left")

        # Signature preview badge
        sig_frame = tk.Frame(card_info, bg="#F8FAFC", relief="solid", bd=1, padx=10, pady=6)
        sig_frame.pack(fill="x", pady=(8, 0))
        tk.Label(sig_frame, text="Email Signature Included at End:", font=("Segoe UI", 8, "bold"), fg="#64748B", bg="#F8FAFC").pack(anchor="w")
        tk.Label(sig_frame, text="Kareem Elebairy\nIEEE Computer Society Vice Chair", font=("Segoe UI", 9, "bold"), fg="#00629B", justify="left", bg="#F8FAFC").pack(anchor="w")

        # 3. Test Email Verification Card
        card_test = tk.LabelFrame(
            self.tab_mailer,
            text=" 3. Anti-Spam Inbox Test (Send 1 Test Email) ",
            font=("Segoe UI", 10, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            padx=15,
            pady=10,
            relief="solid",
            bd=1
        )
        card_test.pack(fill="x", pady=(0, 8))

        row_t = tk.Frame(card_test, bg="#FFFFFF")
        row_t.pack(fill="x")

        tk.Label(row_t, text="Send Test Pass To:", font=("Segoe UI", 9), bg="#FFFFFF").pack(side="left", padx=(0, 8))
        tk.Entry(row_t, textvariable=self.test_email_var, font=("Segoe UI", 9), bg="#F8FAFC", relief="solid", bd=1, width=34).pack(side="left", padx=(0, 12))

        self.btn_test_send = tk.Button(
            row_t,
            text="Send Test Email to Me",
            command=self.start_test_email,
            font=("Segoe UI", 9, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2"
        )
        self.btn_test_send.pack(side="left")

        lbl_test_hint = tk.Label(
            card_test,
            text="Check your inbox to confirm the pass arrives directly in Primary Inbox (not Spam) before sending to everyone.",
            font=("Segoe UI", 8),
            fg="#64748B",
            bg="#FFFFFF"
        )
        lbl_test_hint.pack(anchor="w", pady=(4, 0))

        # 4. Batch Dispatch & Live Log
        card_send = tk.LabelFrame(
            self.tab_mailer,
            text=" 4. Batch Dispatch to All Attendees ",
            font=("Segoe UI", 10, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            padx=12,
            pady=10,
            relief="solid",
            bd=1
        )
        card_send.pack(fill="both", expand=True)

        row_act = tk.Frame(card_send, bg="#FFFFFF")
        row_act.pack(fill="x", pady=(0, 6))

        chk_skip = tk.Checkbutton(
            row_act,
            text="Skip already sent attendees (resume mode)",
            variable=self.skip_sent_var,
            font=("Segoe UI", 9),
            bg="#FFFFFF"
        )
        chk_skip.pack(side="left")

        self.btn_batch_send = tk.Button(
            row_act,
            text="🚀 Send Passes to All Attendees",
            command=self.start_batch_send,
            font=("Segoe UI", 10, "bold"),
            bg="#00629B",
            fg="#FFFFFF",
            relief="flat",
            padx=18,
            pady=5,
            cursor="hand2"
        )
        self.btn_batch_send.pack(side="right")

        self.mail_prog = ttk.Progressbar(card_send, orient="horizontal", mode="determinate")
        self.mail_prog.pack(fill="x", pady=(0, 6))

        # Live log text box
        self.log_text = tk.Text(card_send, height=6, bg="#0F172A", fg="#F8FAFC", font=("Consolas", 8), relief="flat")
        self.log_text.pack(fill="both", expand=True)
        self.log_msg("Ready to send. Enter your credentials and run a Test Email first.")

    def log_msg(self, msg: str):
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")

    def toggle_pwd_visibility(self):
        if self.show_pwd_var.get():
            self.entry_pwd.config(show="")
        else:
            self.entry_pwd.config(show="*")

    # ==========================================================================
    # Logic: CSV Loading & Generation
    # ==========================================================================
    def browse_csv(self):
        f = filedialog.askopenfilename(
            title="Select Attendee CSV",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if f:
            self.csv_path_var.set(f)
            self.load_csv_preview(f)

    def create_sample(self):
        try:
            p = create_sample_csv("sample_attendees.csv")
            self.csv_path_var.set(p)
            self.load_csv_preview(p)
            messagebox.showinfo("Sample Created", f"Sample CSV created at:\n{p}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_csv_preview(self, filepath: str):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not os.path.exists(filepath):
            return

        try:
            df = pd.read_csv(filepath, dtype=str, index_col=False)
            col_map = detect_columns(df)

            for i, (_, row) in enumerate(df.iterrows()):
                name = str(row[col_map['name']]).strip()
                number = str(row[col_map['number']]).strip()
                is_ieee = parse_ieee_status(row[col_map['ieee']]) if 'ieee' in col_map else False
                email = str(row[col_map['email']]).strip() if 'email' in col_map and not pd.isna(row[col_map['email']]) else ""
                pass_id = str(1001 + i)

                status_txt = "★ YES" if is_ieee else "• NO"
                self.tree.insert("", "end", values=(pass_id, name, number, status_txt, email))

            self.gen_status_var.set(f"Loaded {len(df)} attendees from {os.path.basename(filepath)}. Ready to generate.")
        except Exception as e:
            self.gen_status_var.set(f"Error reading CSV: {e}")

    def start_generation(self):
        csv_p = self.csv_path_var.get().strip()
        if not csv_p or not os.path.exists(csv_p):
            messagebox.showwarning("Missing CSV", "Please select a valid CSV file.")
            return

        out_d = self.output_dir_var.get().strip() or "output_qrs"
        fmt = self.format_var.get()
        badges = self.generate_badges_var.get()

        self.btn_generate.config(state="disabled")
        self.gen_prog.start(10)
        self.gen_status_var.set("Generating QR passes and badges... please wait.")

        def worker():
            try:
                res = process_attendees(
                    csv_path=csv_p,
                    output_dir=out_d,
                    payload_format=fmt,
                    create_badges=badges
                )
                self.after(0, lambda: self.on_gen_success(res))
            except Exception as e:
                self.after(0, lambda: self.on_gen_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_gen_success(self, res: dict):
        self.gen_prog.stop()
        self.btn_generate.config(state="normal")
        self.gen_status_var.set(f"Generated {res['total']} passes in '{res['qr_dir']}'!")
        msg = (
            f"Successfully generated {res['total']} attendee passes!\n\n"
            f"• Pass IDs are purely numeric (1001 - {1000 + res['total']})\n"
            f"• Phone numbers removed from badges\n"
            f"• Registry CSV saved to: {res['registry_csv']}\n\n"
            f"You can now switch to the 'Send Passes by Email' tab to email the badges."
        )
        messagebox.showinfo("Passes Generated", msg)

    def on_gen_error(self, err: str):
        self.gen_prog.stop()
        self.btn_generate.config(state="normal")
        self.gen_status_var.set(f"Error: {err}")
        messagebox.showerror("Generation Error", err)

    def open_output_folder(self):
        d = os.path.abspath(self.output_dir_var.get().strip() or "output_qrs")
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(d)
        else:
            subprocess.run(["open", d])

    # ==========================================================================
    # Logic: Email Sending
    # ==========================================================================
    def start_test_email(self):
        sender = self.sender_email_var.get().strip()
        pwd = self.sender_pwd_var.get().strip()
        test_to = self.test_email_var.get().strip()

        # If test_to is empty, automatically default to sender
        if not test_to and sender:
            test_to = sender
            self.test_email_var.set(sender)

        if not sender or "@" not in sender:
            messagebox.showwarning(
                "Missing Sender Email",
                "Please enter your Sender Email (e.g. your_email@gmail.com) in Section 1."
            )
            return

        if not pwd:
            messagebox.showwarning(
                "Missing App Password",
                "Please enter your 16-character Google App Password in Section 1.\n\n"
                "(Note: This is an App Password generated from Google Account Security, NOT your normal password)."
            )
            return

        if not test_to or "@" not in test_to:
            messagebox.showwarning(
                "Missing Test Recipient Email",
                "Please enter a recipient email address in the 'Send Test Pass To' box in Section 3."
            )
            return

        self.btn_test_send.config(state="disabled")
        self.log_msg(f"[*] Sending test pass to {test_to}...")

        def worker():
            try:
                res = batch_send_passes(
                    registry_csv=os.path.join(self.output_dir_var.get().strip() or "output_qrs", "attendees_registry.csv"),
                    badge_dir=os.path.join(self.output_dir_var.get().strip() or "output_qrs", "badges"),
                    sender_email=sender,
                    sender_password=pwd,
                    smtp_host=self.smtp_host_var.get().strip(),
                    smtp_port=self.smtp_port_var.get(),
                    sender_name=self.sender_name_var.get().strip(),
                    event_name=self.event_name_var.get().strip(),
                    test_mode_email=test_to
                )
                self.after(0, lambda: self.on_test_success(test_to))
            except Exception as e:
                self.after(0, lambda: self.on_mail_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_test_success(self, test_to: str):
        self.btn_test_send.config(state="normal")
        self.log_msg(f"[SUCCESS] Test pass delivered to {test_to}!")
        messagebox.showinfo(
            "Test Email Sent",
            f"Test email was successfully sent to:\n{test_to}\n\n"
            f"Please check your inbox (and spam folder) to verify that it arrived in your Primary Inbox."
        )

    def start_batch_send(self):
        sender = self.sender_email_var.get().strip()
        pwd = self.sender_pwd_var.get().strip()

        if not sender or "@" not in sender:
            messagebox.showwarning(
                "Missing Sender Email",
                "Please enter your Sender Email (e.g. your_email@gmail.com) in Section 1."
            )
            return

        if not pwd:
            messagebox.showwarning(
                "Missing App Password",
                "Please enter your 16-character Google App Password in Section 1."
            )
            return

        reg_csv = os.path.join(self.output_dir_var.get().strip() or "output_qrs", "attendees_registry.csv")
        if not os.path.exists(reg_csv):
            messagebox.showerror("Registry Not Found", f"Cannot find {reg_csv}. Please generate passes first in Tab 1.")
            return

        df = pd.read_csv(reg_csv, dtype=str)
        confirm = messagebox.askyesno(
            "Confirm Email Dispatch",
            f"Are you sure you want to send passes to {len(df)} attendees?\n\n"
            f"Anti-spam delay: {self.delay_var.get()}s between emails.\n"
            f"Sender: {sender}\n"
            f"Signature: Kareem Elebairy (IEEE CS Vice Chair)"
        )
        if not confirm:
            return

        self.btn_batch_send.config(state="disabled")
        self.mail_prog["maximum"] = len(df)
        self.mail_prog["value"] = 0
        self.log_msg(f"[*] Starting batch dispatch to {len(df)} attendees...")

        def progress_cb(current, total, name, email):
            self.after(0, lambda: self.update_batch_progress(current, total, name, email))

        def worker():
            try:
                res = batch_send_passes(
                    registry_csv=reg_csv,
                    badge_dir=os.path.join(self.output_dir_var.get().strip() or "output_qrs", "badges"),
                    sender_email=sender,
                    sender_password=pwd,
                    smtp_host=self.smtp_host_var.get().strip(),
                    smtp_port=self.smtp_port_var.get(),
                    sender_name=self.sender_name_var.get().strip(),
                    event_name=self.event_name_var.get().strip(),
                    delay_seconds=self.delay_var.get(),
                    skip_already_sent=self.skip_sent_var.get(),
                    progress_callback=progress_cb
                )
                self.after(0, lambda: self.on_batch_success(res))
            except Exception as e:
                self.after(0, lambda: self.on_mail_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def update_batch_progress(self, current, total, name, email):
        self.mail_prog["value"] = current
        self.log_msg(f"[{current}/{total}] Sent pass to: {name} <{email}>")

    def on_batch_success(self, res: dict):
        self.btn_batch_send.config(state="normal")
        self.log_msg(f"[DONE] Dispatch complete! Sent: {res['success']}, Skipped: {res['skipped']}, Failed: {res['failed']}")
        messagebox.showinfo(
            "Dispatch Complete",
            f"Email dispatch completed!\n\n"
            f"• Successfully sent: {res['success']}\n"
            f"• Skipped: {res['skipped']}\n"
            f"• Failed: {res['failed']}\n\n"
            f"Registry updated with timestamps in output_qrs/attendees_registry.csv"
        )

    def on_mail_error(self, err: str):
        self.btn_test_send.config(state="normal")
        self.btn_batch_send.config(state="normal")
        self.log_msg(f"[ERROR] {err}")
        messagebox.showerror("Email Error", f"An error occurred during email transmission:\n\n{err}")


def launch_gui():
    app = IEEEEventApp()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
