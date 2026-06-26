"""
StripeToQBO — Convert Stripe CSV export to QuickBooks Online format.
MVP for bootstrappers. Single file, zero database, zero OAuth.
"""

import streamlit as st
import pandas as pd
import re
from extra_streamlit_components import CookieManager
from datetime import datetime

# ─── PAGE CONFIGURATION ────────────────────────────────────────────
st.set_page_config(
    page_title="StripeToQBO — Stripe CSV → QuickBooks",
    page_icon="🔄",
    layout="centered",
)

# ─── COOKIE MANAGEMENT ─────────────────────────────────────────────
cookie_manager = CookieManager()
free_used_cookie = cookie_manager.get("stripe_to_qbo_free_used")

# ─── ACCESS CONTROL ────────────────────────────────────────────────
if "access_granted" not in st.session_state:
    st.session_state.access_granted = False
if "free_used" not in st.session_state:
    st.session_state.free_used = (free_used_cookie == "true")

ACCESS_CODE = st.secrets.get("ACCESS_CODE", None)

# Password-protected mode (optional)
if ACCESS_CODE and not st.session_state.access_granted:
    st.title("🔒 StripeToQBO")
    st.markdown("### Enter your access code to use the tool.")
    code_input = st.text_input("Access code", type="password")
    if st.button("Unlock"):
        if code_input == ACCESS_CODE:
            st.session_state.access_granted = True
            st.rerun()
        else:
            st.error("Invalid code. Purchase access on our website.")
    st.stop()

# Free trial mode — one conversion per browser (cookie-based)
if not st.session_state.access_granted and st.session_state.free_used:
    st.warning("⚠️ You've already used your free conversion on this device.")
    st.markdown("### 💳 Get Full Access")
    st.link_button("🛒 Buy Solo Plan — $15/month", "https://buy.stripe.com/test_3cI3cudQkeHu0IJgeQ3ZK00")
    st.link_button("🛒 Buy Pro Plan — $29/month", "https://buy.stripe.com/test_3cI9ASbIcczmezz2o03ZK01")
    st.stop()

# ─── HELPER FUNCTIONS ──────────────────────────────────────────────

def clean_amount(val) -> float:
    """Clean currency strings into floats. Handles $, €, commas, etc."""
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return 0.0
    s = val.strip()
    s = re.sub(r'[^\d,.\-]', '', s)
    if ',' in s and '.' in s:
        s = s.replace(',', '')
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0

def parse_date(val):
    """Parse dates from various Stripe export formats."""
    if isinstance(val, datetime):
        return val
    if not isinstance(val, str):
        return None
    s = val.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return pd.to_datetime(s).to_pydatetime()
    except Exception:
        return None

def detect_stripe_format(df: pd.DataFrame) -> dict:
    """Detect column names in the Stripe CSV."""
    cols_lower = {c.lower(): c for c in df.columns}
    mapping = {"date_col": None, "desc_col": None, "amount_col": None, "fee_col": None}

    for key in ["created (utc)", "created", "date (utc)", "date"]:
        if key in cols_lower:
            mapping["date_col"] = cols_lower[key]
            break
    for key in ["description", "desc", "name", "statement descriptor"]:
        if key in cols_lower:
            mapping["desc_col"] = cols_lower[key]
            break
    for key in ["amount", "gross", "total", "amount (gross)"]:
        if key in cols_lower:
            mapping["amount_col"] = cols_lower[key]
            break
    for key in ["fee", "stripe fee", "processing fee", "fees"]:
        if key in cols_lower:
            mapping["fee_col"] = cols_lower[key]
            break
    return mapping

def convert_stripe_to_qbo(df: pd.DataFrame) -> pd.DataFrame:
    """Convert Stripe CSV rows to QBO-compatible format (revenue + fee split)."""
    mapping = detect_stripe_format(df)

    if not mapping["date_col"]:
        st.error("❌ Could not find a date column. Make sure this is a Stripe CSV export.")
        st.stop()
    if not mapping["amount_col"]:
        st.error("❌ Could not find an amount column. Make sure this is a Stripe CSV export.")
        st.stop()

    qbo_rows = []
    for _, row in df.iterrows():
        date_val = parse_date(row[mapping["date_col"]])
        date_str = date_val.strftime("%m/%d/%Y") if date_val else ""
        desc_val = str(row.get(mapping["desc_col"], "Stripe Payment")) if mapping["desc_col"] else "Stripe Payment"
        desc_val = desc_val[:100]
        amount = clean_amount(row[mapping["amount_col"]])
        fee = clean_amount(row[mapping["fee_col"]]) if mapping["fee_col"] else 0.0

        qbo_rows.append({
            "Date": date_str,
            "Description": f"Payment: {desc_val}",
            "Amount": f"{amount:.2f}",
            "Account": "Sales / Income",
        })
        if fee > 0:
            qbo_rows.append({
                "Date": date_str,
                "Description": f"Stripe Fee: {desc_val}",
                "Amount": f"-{fee:.2f}",
                "Account": "Payment Processing Fees",
            })
    return pd.DataFrame(qbo_rows)

# ─── USER INTERFACE ─────────────────────────────────────────────────

st.title("🔄 StripeToQBO")
st.caption("Convert your Stripe CSV export to QuickBooks Online format in 10 seconds.")

if not st.session_state.access_granted:
    st.info("💡 **1 free conversion** — try it out. Full access: $15/month.")

uploaded_file = st.file_uploader(
    "📂 Upload your Stripe CSV export",
    type=["csv"],
    help="In the Stripe Dashboard: Payments → Export → CSV. Or Balance → Export.",
)

if uploaded_file is not None:
    try:
        df_raw = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"❌ Could not read CSV file: {e}")
        st.stop()

    st.success(f"✅ Loaded {len(df_raw)} transactions.")

    with st.expander("📋 Preview of your Stripe file"):
        st.dataframe(df_raw.head(10), use_container_width=True)
        st.caption(f"Columns: {', '.join(df_raw.columns.tolist())}")

    if st.button("⚡ Convert to QuickBooks", type="primary"):
        with st.spinner("Converting..."):
            try:
                df_qbo = convert_stripe_to_qbo(df_raw)
            except Exception as e:
                st.error(f"❌ Conversion error: {e}")
                st.stop()

        st.success(f"🎉 Done! Generated {len(df_qbo)} rows (revenue + fees).")

        with st.expander("📋 Preview of the QuickBooks file"):
            st.dataframe(df_qbo, use_container_width=True)

        csv_output = df_qbo.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV for QuickBooks",
            data=csv_output,
            file_name="quickbooks_import.csv",
            mime="text/csv",
        )

        with st.expander("📖 How to import into QuickBooks Online"):
            st.markdown("""
            1. In QuickBooks Online, go to **Banking → Upload transactions**  
               or **Settings → Import Data → Bank Transactions**.
            2. Choose the downloaded CSV file.
            3. During column mapping, match:
               - **Date** → Date  
               - **Description** → Description  
               - **Amount** → Amount  
            4. Click **Import**.
            5. Assign accounts if needed (Income for revenue, Fees for processing costs).
            """)

        # Mark free trial as used
        if not st.session_state.access_granted:
            cookie_manager.set("stripe_to_qbo_free_used", "true", expires_at=datetime(2036, 12, 31))
            st.session_state.free_used = True
            st.warning("⚠️ That was your only free conversion on this device. Full access is $15/month.")
            st.link_button("🛒 Buy Solo Plan — $15/month", "https://buy.stripe.com/test_3cI3cudQkeHu0IJgeQ3ZK00")

# --- Pricing section ---
if not st.session_state.access_granted:
    st.divider()
    st.markdown("### 💳 Get Full Access")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Solo Plan — $15/month**  
        ✅ 50 conversions per month  
        ✅ Files up to 5 MB  
        ✅ Files deleted immediately after conversion  
        """)
        st.link_button("🛒 Buy Solo Plan", "https://buy.stripe.com/test_3cI3cudQkeHu0IJgeQ3ZK00", type="primary")
    with col2:
        st.markdown("""
        **Pro Plan — $29/month**  
        ✅ Unlimited conversions  
        ✅ Files up to 25 MB  
        ✅ Priority email support  
        """)
        st.link_button("🛒 Buy Pro Plan", "https://buy.stripe.com/test_3cI9ASbIcczmezz2o03ZK01")

st.divider()
st.caption("🔒 Your data is safe. Files are processed in memory and deleted immediately. Nothing is stored on our servers.")
st.caption("© 2026 StripeToQBO | [Terms](#) | [Privacy](#)")
