
import streamlit as st
import os
import smtplib
import secrets

from src.database import (
    get_user_by_email,
    create_password_reset_otp,
    verify_password_reset_otp,
    delete_password_reset_otp,
    reset_user_password
)
from email.message import EmailMessage
from dotenv import load_dotenv
from src.database import (
    register_user,
    get_user_by_username,
    verify_password,
    log_activity
)
load_dotenv()


def send_otp_email(receiver_email, otp):
    sender_email = os.getenv("SMTP_EMAIL")
    app_password = os.getenv("SMTP_APP_PASSWORD")

    if not sender_email or not app_password:
        return False, "Email configuration is missing."

    message = EmailMessage()
    message["Subject"] = "CryptoPulse Password Reset OTP"
    message["From"] = sender_email
    message["To"] = receiver_email

    message.set_content(
        f"""
Hello,

Your CryptoPulse password reset OTP is:

{otp}

This OTP expires in 5 minutes.

If you did not request this password reset,
please ignore this email.

Regards,
CryptoPulse Team
"""
    )

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(message)

        return True, "OTP sent successfully."

    except Exception:
        return False, "Unable to send email. Check your Gmail configuration."
    
def render_forgot_password():
    st.title("🔑 Forgot Password")
    st.caption("Reset your CryptoPulse account password.")

    if "reset_email" not in st.session_state:
        st.session_state["reset_email"] = ""

    if "otp_verified" not in st.session_state:
        st.session_state["otp_verified"] = False

    if "otp_sent" not in st.session_state:
        st.session_state["otp_sent"] = False

    email = st.text_input(
        "Registered email address",
        value=st.session_state["reset_email"],
        disabled=st.session_state["otp_sent"]
    )

    if st.button("Send OTP"):
        email = email.strip().lower()

        user = get_user_by_email(email)

        if not user:
            st.error("Unable to process this request. Check your email or contact support.")
        else:
            otp = f"{secrets.randbelow(1000000):06d}"

            create_password_reset_otp(email, otp)

            success, message = send_otp_email(email, otp)

            if success:
                st.session_state["reset_email"] = email
                st.session_state["otp_sent"] = True
                st.success("OTP sent to your registered email.")
            else:
                delete_password_reset_otp(email)
                st.error(message)

    if st.session_state["otp_sent"]:

        st.divider()
        st.subheader("Verify OTP")

        entered_otp = st.text_input(
            "Enter 6-digit OTP",
            max_chars=6
        )

        if st.button("Verify OTP"):
            if len(entered_otp) != 6 or not entered_otp.isdigit():
                st.error("Enter a valid 6-digit OTP.")
            else:
                valid, message = verify_password_reset_otp(
                    st.session_state["reset_email"],
                    entered_otp
                )

                if valid:
                    st.session_state["otp_verified"] = True
                    st.success("OTP verified successfully!")
                else:
                    st.error(message)

    if st.session_state["otp_verified"]:

        st.divider()
        st.subheader("Create New Password")

        new_password = st.text_input(
            "New password",
            type="password"
        )

        confirm_password = st.text_input(
            "Confirm new password",
            type="password"
        )

        if st.button("Reset Password"):

            if new_password != confirm_password:
                st.error("Passwords do not match.")

            else:
                success, message = reset_user_password(
                    st.session_state["reset_email"],
                    new_password
                )

                if success:
                    st.success(message)

                    for key in [
                        "reset_email",
                        "otp_sent",
                        "otp_verified"
                    ]:
                        st.session_state.pop(key, None)

                    st.info("Return to Login and sign in with your new password.")

                else:
                    st.error(message)



def render_auth_screen():
    """Display login, registration and password recovery screens."""

    st.title("₿ CryptoPulse")
    st.subheader("Welcome to CryptoPulse")
    st.caption("Sign in to access cryptocurrency analytics and predictions.")

    # FORGOT PASSWORD SCREEN
    if st.session_state.get("show_forgot_password", False):

        render_forgot_password()

        if st.button("Back to Login"):
            for key in [
                "show_forgot_password",
                "reset_email",
                "otp_sent",
                "otp_verified"
            ]:
                st.session_state.pop(key, None)

            st.rerun()

        return

    # LOGIN AND REGISTRATION TABS
    login_tab, register_tab = st.tabs(["Login", "Create Account"])

    # LOGIN TAB
    with login_tab:

        st.markdown("### Login to your account")

        with st.form("login_form"):

            username = st.text_input("Username")
            password = st.text_input(
                "Password",
                type="password"
            )

            login_button = st.form_submit_button(
                "Login",
                use_container_width=True
            )

        if login_button:

            user = get_user_by_username(username)

            if user and verify_password(
                password,
                user["password_hash"]
            ):

                st.session_state["current_user"] = {
                    "id": user["id"],
                    "username": user["username"],
                    "role": user["role"]
                }

                log_activity(
                    user["id"],
                    "LOGIN",
                    "User logged in successfully"
                )

                st.success("Login successful!")
                st.rerun()

            else:
                st.error("Invalid username or password.")

        st.divider()

        if st.button("Forgot Password?", use_container_width=True):
            st.session_state["show_forgot_password"] = True
            st.rerun()

    # REGISTRATION TAB
    with register_tab:

        st.markdown("### Create a new account")

        with st.form("register_form"):

            new_username = st.text_input("Choose a username")
            new_email = st.text_input("Email address")

            new_password = st.text_input(
                "Create password",
                type="password"
            )

            confirm_password = st.text_input(
                "Confirm password",
                type="password"
            )

            register_button = st.form_submit_button(
                "Create Account",
                use_container_width=True
            )

        if register_button:

            if new_password != confirm_password:

                st.error("Passwords do not match.")

            else:

                success, message = register_user(
                    new_username,
                    new_email,
                    new_password
                )

                if success:

                    st.success(message)

                    user = get_user_by_username(new_username)

                    if user:
                        log_activity(
                            user["id"],
                            "REGISTER",
                            "New account created"
                        )

                    st.info("You can now log in.")

                else:
                    st.error(message)


def logout_user():
    """Log out the currently authenticated user."""

    user = st.session_state.get("current_user")

    if user:
        log_activity(
            user["id"],
            "LOGOUT",
            "User logged out"
        )

    st.session_state.pop("current_user", None)
    st.rerun()
