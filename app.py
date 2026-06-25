"""
StripeToQBO — konwertuj plik CSV ze Stripe do formatu QuickBooks Online.
MVP dla bootstrappera. Jeden plik, zero bazy danych, zero OAuth.
"""

import streamlit as st
import pandas as pd
import re
import extra_streamlit_components as stx
from datetime import datetime

# ─── KONFIGURACJA STRONY ───────────────────────────────────────────
st.set_page_config(
    page_title="StripeToQBO — Stripe CSV → QuickBooks",
    page_icon="🔄",
    layout="centered",
)

# ─── ZARZĄDZANIE CIASTECZKIEM (COOKIE) ────────────────────────────
@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

# Odczytaj ciasteczko – czy użytkownik już skorzystał z darmowej konwersji
free_used_cookie = cookie_manager.get("stripe_to_qbo_free_used")

# ─── KONTROLA DOSTĘPU ──────────────────────────────────────────────
if "access_granted" not in st.session_state:
    st.session_state.access_granted = False
if "free_used" not in st.session_state:
    # Sprawdź ciasteczko
    st.session_state.free_used = (free_used_cookie == "true")

ACCESS_CODE = st.secrets.get("ACCESS_CODE", None)

# Tryb z kodem dostępu (jeśli ustawiony)
if ACCESS_CODE and not st.session_state.access_granted:
    st.title("🔒 StripeToQBO")
    st.markdown("### Wprowadź kod dostępu, aby korzystać z narzędzia.")
    code_input = st.text_input("Kod dostępu", type="password")
    if st.button("Odblokuj"):
        if code_input == ACCESS_CODE:
            st.session_state.access_granted = True
            st.rerun()
        else:
            st.error("Nieprawidłowy kod. Kup dostęp na stronie produktu.")
    st.stop()

# Tryb darmowy – jeden raz (na podstawie ciasteczka)
if not st.session_state.access_granted and st.session_state.free_used:
    st.warning("⚠️ Wykorzystałeś już darmową konwersję na tym urządzeniu.")
    st.markdown("### 💳 Kup pełny dostęp")
    st.link_button("🛒 Kup Plan Solo — 59 zł / miesiąc", "https://buy.stripe.com/test_3cI3cudQkeHu0IJgeQ3ZK00")
    st.link_button("🛒 Kup Plan Pro — 119 zł / miesiąc", "https://buy.stripe.com/test_3cI9ASbIcczmezz2o03ZK01")
    st.stop()

# ─── FUNKCJE POMOCNICZE ────────────────────────────────────────────

def clean_amount(val) -> float:
    """
    Czyści kwotę z waluty, spacji i zamienia przecinki na kropki.
    Obsługuje: '$10.00', '10,00 zł', '-$5.00', '1,234.56', '€9.99'
    """
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
    """
    Parsuje datę z różnych formatów zwracanych przez Stripe.
    Obsługuje: '2026-06-15', '2026-06-15 14:30:00', '06/15/2026', itp.
    """
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
    """Wykrywa kolumny w pliku CSV Stripe."""
    cols_lower = {c.lower(): c for c in df.columns}
    mapping = {"date_col": None, "desc_col": None, "amount_col": None, "fee_col": None}

    for key in ["created (utc)", "created", "date (utc)", "date", "created (utc)"]:
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
    """Konwertuje CSV Stripe na format QBO."""
    mapping = detect_stripe_format(df)

    if not mapping["date_col"]:
        st.error("❌ Nie znaleziono kolumny z datą. Upewnij się, że to plik CSV ze Stripe.")
        st.stop()
    if not mapping["amount_col"]:
        st.error("❌ Nie znaleziono kolumny z kwotą. Upewnij się, że to plik CSV ze Stripe.")
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

# ─── INTERFEJS UŻYTKOWNIKA ────────────────────────────────────────

st.title("🔄 StripeToQBO")
st.caption("Konwertuj plik CSV ze Stripe do formatu QuickBooks Online w 10 sekund.")

if not st.session_state.access_granted:
    st.info("💡 **1 darmowa konwersja** — wypróbuj za darmo. Pełny dostęp: 59 zł / miesiąc.")

uploaded_file = st.file_uploader(
    "📂 Wrzuć plik CSV wyeksportowany ze Stripe",
    type=["csv"],
    help="W panelu Stripe: Payments → Export → CSV. Albo Balance → Export.",
)

if uploaded_file is not None:
    try:
        df_raw = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"❌ Nie udało się wczytać pliku CSV: {e}")
        st.stop()

    st.success(f"✅ Wczytano {len(df_raw)} transakcji.")

    with st.expander("📋 Podgląd oryginalnego pliku Stripe"):
        st.dataframe(df_raw.head(10), use_container_width=True)
        st.caption(f"Kolumny: {', '.join(df_raw.columns.tolist())}")

    if st.button("⚡ Konwertuj do QuickBooks", type="primary"):
        with st.spinner("Konwertuję..."):
            try:
                df_qbo = convert_stripe_to_qbo(df_raw)
            except Exception as e:
                st.error(f"❌ Błąd konwersji: {e}")
                st.stop()

        st.success(f"🎉 Gotowe! Wygenerowano {len(df_qbo)} wierszy (przychody + opłaty).")

        with st.expander("📋 Podgląd pliku dla QuickBooks"):
            st.dataframe(df_qbo, use_container_width=True)

        csv_output = df_qbo.to_csv(index=False)
        st.download_button(
            label="📥 Pobierz plik CSV dla QuickBooks",
            data=csv_output,
            file_name="quickbooks_import.csv",
            mime="text/csv",
        )

        with st.expander("📖 Jak zaimportować do QuickBooks Online?"):
            st.markdown("""
            1. W QuickBooks Online przejdź do **Banking → Upload transactions**  
               lub **Settings → Import Data → Bank Transactions**.
            2. Wybierz pobrany plik CSV.
            3. W kroku mapowania kolumn dopasuj:
               - **Date** → Date  
               - **Description** → Description  
               - **Amount** → Amount  
            4. Kliknij **Import**.
            5. W razie potrzeby przypisz konta księgowe (Income do przychodów, Fees do kosztów).
            """)

        # Oznacz darmową konwersję jako wykorzystaną
        if not st.session_state.access_granted:
            cookie_manager.set("stripe_to_qbo_free_used", "true", expires_at=datetime(2036, 12, 31))
            st.session_state.free_used = True
            st.warning("⚠️ To była Twoja jedyna darmowa konwersja na tym urządzeniu. Kup pełny dostęp za 59 zł / miesiąc.")
            st.link_button("🛒 Kup Plan Solo — 59 zł / miesiąc", "https://buy.stripe.com/test_3cI3cudQkeHu0IJgeQ3ZK00")

# --- Sekcja: Kup dostęp ---
if not st.session_state.access_granted:
    st.divider()
    st.markdown("### 💳 Kup pełny dostęp")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Plan Solo — 59 zł / miesiąc**  
        ✅ 50 konwersji miesięcznie  
        ✅ Obsługa plików do 5 MB  
        ✅ Pliki usuwane natychmiast po konwersji  
        """)
        st.link_button("🛒 Kup Plan Solo", "https://buy.stripe.com/test_3cI3cudQkeHu0IJgeQ3ZK00", type="primary")
    with col2:
        st.markdown("""
        **Plan Pro — 119 zł / miesiąc**  
        ✅ Nielimitowane konwersje  
        ✅ Obsługa plików do 25 MB  
        ✅ Priorytetowe wsparcie email  
        """)
        st.link_button("🛒 Kup Plan Pro", "https://buy.stripe.com/test_3cI9ASbIcczmezz2o03ZK01")

st.divider()
st.caption("🔒 Twoje dane są bezpieczne. Pliki są usuwane natychmiast po konwersji. Nie przechowujemy ich na serwerze.")
st.caption("© 2026 StripeToQBO | [Regulamin](#) | [Polityka prywatności](#)")
