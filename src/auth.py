
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
    # Read credentials from Streamlit Cloud Secrets first
    try:
        sender_email = st.secrets.get(
            "SMTP_EMAIL", os.getenv("SMTP_EMAIL")
        )
        app_password = st.secrets.get(
            "SMTP_APP_PASSWORD", os.getenv("SMTP_APP_PASSWORD")
        )

    except Exception:
        # Fallback for local development using .env
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

    except Exception as e:
        print(f"Email error: {e}")
        return False, "Unable to send email. Check your Gmail configuration."


def apply_auth_styles():
    st.markdown("""
    <style>
    /* Main background */
    .stApp {
        background:
            radial-gradient(ellipse at 15% 10%, rgba(92, 61, 180, 0.20), transparent 40%),
            radial-gradient(ellipse at 85% 85%, rgba(25, 105, 180, 0.16), transparent 40%),
            #080d19;
    }

    /* Main content width */
    .main .block-container {
        max-width: 720px;
        padding-top: 3rem;
        padding-bottom: 3rem;
    }

    /* Branding */
    h1 {
        color: #ffffff !important;
        font-weight: 800 !important;
        letter-spacing: -1.5px;
    }

    h2, h3 {
        color: #f1f5ff !important;
    }

    p, label, .stMarkdown {
        color: #c4cbe0;
    }

    /* Forms and containers */
    div[data-testid="stForm"],
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(19, 27, 46, 0.78);
        border: 1px solid rgba(139, 125, 255, 0.20);
        border-radius: 16px;
        padding: 18px;
    }

    /* Input fields */
    .stTextInput input {
        background: #111a2d !important;
        color: #ffffff !important;
        border: 1px solid #303c58 !important;
        border-radius: 9px !important;
    }

    .stTextInput input:focus {
        border-color: #9278ff !important;
        box-shadow: 0 0 0 1px #9278ff !important;
    }

    /* Buttons */
    .stButton button,
    .stFormSubmitButton button {
        background: linear-gradient(100deg, #7655e8, #3979df);
        color: white !important;
        border: none;
        border-radius: 9px;
        font-weight: 650;
        min-height: 43px;
        transition: 0.2s ease;
    }

    .stButton button:hover,
    .stFormSubmitButton button:hover {
        border: 1px solid #b6a4ff;
        filter: brightness(1.12);
    }

    /* Login and registration tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        border-bottom: 1px solid #29344d;
    }

    .stTabs [data-baseweb="tab"] {
        color: #aeb9d1;
        font-weight: 600;
    }

    .stTabs [aria-selected="true"] {
        color: #a995ff !important;
    }

    /* Dividers */
    hr {
        border-color: #29344d !important;
    }

    /* Alerts */
    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    </style>
    """, unsafe_allow_html=True)


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
    """Modern CryptoPulse authentication screen."""

    st.markdown("""
    <style>
    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #07152e, #102b55, #07152e);
        color: white;
    }

    .block-container {
        max-width: 1250px;
        padding-top: 3rem;
        padding-bottom: 2rem;
    }

    /* Branding */
    .brand-title {
        color: white;
        font-size: 40px;
        font-weight: 800;
        letter-spacing: -1px;
        margin-bottom: 5px;
    }

    .brand-subtitle {
        color: #a9c5ed;
        font-size: 15px;
        margin-bottom: 28px;
    }

    /* Login and registration form cards */
    div[data-testid="stForm"] {
        background: #dcecff;
        padding: 25px;
        border-radius: 18px;
        border: 1px solid #a8c9ef;
        box-shadow: 0 12px 30px rgba(0,0,0,0.18);
    }

    div[data-testid="stForm"] label {
        color: #10264a !important;
        font-weight: 600;
    }

    div[data-testid="stForm"] input {
        background: #f7faff !important;
        color: #10264a !important;
        border: 1px solid #b4cdec !important;
        border-radius: 9px !important;
    }

    /* Buttons */
    .stButton button,
    .stFormSubmitButton button {
        background: linear-gradient(90deg, #2878e8, #5b9cff);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        min-height: 43px;
        transition: 0.2s ease;
    }

    .stButton button:hover,
    .stFormSubmitButton button:hover {
        background: #1765d0;
        color: white;
        border: none;
        transform: translateY(-2px);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab"] {
        color: #c9ddfa;
        font-weight: 700;
    }

    .stTabs [aria-selected="true"] {
        color: white !important;
    }

    /* Right-side panel */
    .crypto-heading {
        color: white;
        font-size: 29px;
        font-weight: 800;
        margin-bottom: 8px;
    }

    .crypto-subtitle {
        color: #a9c5ed;
        font-size: 14px;
        line-height: 1.7;
    }

    .crypto-banner {
        background: linear-gradient(135deg, #173d72, #091b38);
        padding: 30px 20px;
        border-radius: 20px;
        text-align: center;
        border: 1px solid #386ba8;
        box-shadow: 0 12px 35px rgba(0,0,0,0.25);
        margin-top: 20px;
        margin-bottom: 22px;
    }

    .crypto-symbol {
        font-size: 75px;
        margin-bottom: 5px;
    }

    .crypto-banner-title {
        color: white;
        font-size: 27px;
        font-weight: 800;
    }

    .crypto-banner-text {
        color: #b9d5f5;
        font-size: 14px;
    }

    /* Market asset cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #173d72, #10294d);
        padding: 16px;
        border-radius: 14px;
        border: 1px solid #315d91;
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
    }

    div[data-testid="stMetricLabel"] {
        color: #a9c5ed !important;
    }

    div[data-testid="stMetricValue"] {
        color: white !important;
        font-size: 22px !important;
    }

    /* Information messages */
    div[data-testid="stAlert"] {
        border-radius: 12px;
    }

    @media (max-width: 750px) {
        .brand-title {
            font-size: 32px;
        }

        .crypto-heading {
            font-size: 24px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1.1], gap="large")

    # LEFT SIDE: AUTHENTICATION
    with left_col:

        st.markdown(
            '<div class="brand-title">₿ CryptoPulse</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="brand-subtitle">'
            'Your gateway to smarter cryptocurrency insights.'
            '</div>',
            unsafe_allow_html=True
        )

        # Forgot password
        if st.session_state.get("show_forgot_password", False):

            render_forgot_password()

            if st.button("← Back to Login", use_container_width=True):
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
        login_tab, register_tab = st.tabs(
            ["Login", "Create Account"]
        )

        # LOGIN
        with login_tab:

            st.markdown("### Welcome Back")
            st.caption("Sign in to continue to your dashboard.")

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

            if st.button(
                "Forgot Password?",
                use_container_width=True
            ):
                st.session_state["show_forgot_password"] = True
                st.rerun()

        # REGISTRATION
        with register_tab:

            st.markdown("### Create Your Account")
            st.caption("Join CryptoPulse and explore crypto analytics.")

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

    # RIGHT SIDE: CRYPTO SHOWCASE
    with right_col:

        st.markdown(
            '<div class="crypto-heading">'
            'Explore the Crypto World'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="crypto-subtitle">'
            'Discover digital assets and explore the cryptocurrency market.'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown("""
        <div class="crypto-banner">
            <div class="crypto-symbol">₿</div>
            <div class="crypto-banner-title">CryptoPulse</div>
            <p class="crypto-banner-text">
                Track markets. Discover trends. Make smarter decisions.
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("#### Popular Cryptocurrencies")

        asset1, asset2, asset3 = st.columns(3)

        with asset1:
            st.metric("₿ BITCOIN", "BTC")

        with asset2:
            st.metric("Ξ ETHEREUM", "ETH")

        with asset3:
            st.metric("◎ SOLANA", "SOL")

        st.write("")

        st.info(
            "📊 Explore cryptocurrency prices, market trends "
            "and analytics with CryptoPulse."
        )





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
