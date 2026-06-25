"""
StripeToQBO — konwertuj plik CSV ze Stripe do formatu QuickBooks Online.
MVP dla bootstrappera. Jeden plik, zero bazy danych, zero OAuth.
"""

import streamlit as st
import pandas as pd
import io
import re
import hashlib
from datetime import datetime

# ─── KONFIGURACJA STRONY ───────────────────────────────────────────
st.set_page_config(
    page_title="StripeToQBO — Stripe CSV → QuickBooks",
    page_icon="🔄",
    layout="centered",
)

# ─── FUNKCJA POBIERAJĄCA IP UŻYTKOWNIKA ────────────────────────────
def get_client_ip():
    """Pobiera adres IP klienta ze Streamlit."""
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    ctx = get_script_run_ctx()
    if ctx and hasattr(ctx, 'session_info') and ctx.session_info:
        return ctx.session_info.get('client_ip', 'unknown')
    return 'unknown'

# ─── KONTROLA DOSTĘPU ──────────────────────────────────────────────
if "access_granted" not in st.session_state:
    st.session_state.access_granted = False
if "used_ips" not in st.session_state:
    st.session_state.used_ips = set()
if "free_used_this_session" not in st.session_state:
    st.session_state.free_used_this_session = False

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

# Tryb darmowy – jeden raz na IP
if not st.session_state.access_granted:
    client_ip = get_client_ip()

    if client_ip not in st.session_state.used_ips and not st.session_state.free_used_this_session:
        st.info("💡 **1 darmowa konwersja** — wypróbuj za darmo. Pełny dostęp: 59 zł / miesiąc.")
    elif st.session_state.free_used_this_session:
        # Użytkownik już skorzystał w tej sesji
        pass  # komunikat pojawi się po konwersji
    else:
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
    # Usuń symbole walut i spacje
    s = re.sub(r'[^\d,.\-]', '', s)
    # Jeśli jest i przecinek i kropka — przecinek to separator tysięcy
    if ',' in s and '.' in s:
        s = s.replace(',', '')
    # Jeśli tylko przecinek — to separator dziesiętny
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
    # Próbuj pandas
    try:
        return pd.to_datetime(s).to_pydatetime()
    except Exception:
        return None

def detect_stripe_format(df: pd.DataFrame) -> dict:
    """
    Wykrywa kolumny w pliku CSV Stripe.
    Zwraca słownik z mapowaniem: {'date_col': '...', 'desc_col': '...', ...}
    """
    cols_lower = {c.lower(): c for c in df.columns}

    mapping = {"date_col": None, "desc_col": None, "amount_col": None, "fee_col": None}

    # Data — szukamy 'created', 'date', 'date (utc)'
    for key in ["created (utc)", "created", "date (utc)", "date", "created (utc)"]:
        if key in cols_lower:
            mapping["date_col"] = cols_lower[key]
            break

    # Opis
    for key in ["description", "desc", "name", "statement descriptor"]:
        if key in cols_lower:
            mapping["desc_col"] = cols_lower[key]
            break

    # Kwota brutto
    for key in ["amount", "gross", "total", "amount (gross)"]:
        if key in cols_lower:
            mapping["amount_col"] = cols_lower[key]
            break

    # Opłata Stripe
    for key in ["fee", "stripe fee", "processing fee", "fees"]:
        if key in cols_lower:
            mapping["fee_col"] = cols_lower[key]
            break

    return mapping

def convert_stripe_to_qbo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Główna funkcja konwersji. Dla każdego wiersza w CSV Stripe tworzy
    DWA wiersze w formacie QBO: przychód i opłatę.
    """
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
        desc_val = desc_val[:100]  # Limit, żeby nie łamać QBO

        amount = clean_amount(row[mapping["amount_col"]])
        fee = clean_amount(row[mapping["fee_col"]]) if mapping["fee_col"] else 0.0

        # Rząd 1: Przychód (kwota brutto, dodatnia)
        qbo_rows.append({
            "Date": date_str,
            "Description": f"Payment: {desc_val}",
            "Amount": f"{amount:.2f}",
            "Account": "Sales / Income",  # Sugestia — użytkownik mapuje w QBO
        })

        # Rząd 2: Opłata Stripe (ujemna, jako koszt)
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

# --- Upload pliku ---
uploaded_file = st.file_uploader(
    "📂 Wrzuć plik CSV wyeksportowany ze Stripe",
    type=["csv"],
    help="W panelu Stripe: Payments → Export → CSV. Albo Balance → Export.",
)

if uploaded_file is not None:
    # Wczytaj CSV
    try:
        df_raw = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"❌ Nie udało się wczytać pliku CSV: {e}")
        st.stop()

    st.success(f"✅ Wczytano {len(df_raw)} transakcji.")

    # Podgląd oryginalnych danych
    with st.expander("📋 Podgląd oryginalnego pliku Stripe"):
        st.dataframe(df_raw.head(10), use_container_width=True)
        st.caption(f"Kolumny: {', '.join(df_raw.columns.tolist())}")

    # Konwersja
    if st.button("⚡ Konwertuj do QuickBooks", type="primary"):
        with st.spinner("Konwertuję..."):
            try:
                df_qbo = convert_stripe_to_qbo(df_raw)
            except Exception as e:
                st.error(f"❌ Błąd konwersji: {e}")
                st.stop()

        st.success(f"🎉 Gotowe! Wygenerowano {len(df_qbo)} wierszy (przychody + opłaty).")

        # Podgląd wyniku
        with st.expander("📋 Podgląd pliku dla QuickBooks"):
            st.dataframe(df_qbo, use_container_width=True)

        # Pobieranie
        csv_output = df_qbo.to_csv(index=False)
        st.download_button(
            label="📥 Pobierz plik CSV dla QuickBooks",
            data=csv_output,
            file_name="quickbooks_import.csv",
            mime="text/csv",
        )

        # Instrukcja importu
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

        # Free trial — oznacz IP jako użyty
        if not st.session_state.access_granted and not st.session_state.free_used_this_session:
            client_ip = get_client_ip()
            st.session_state.used_ips.add(client_ip)
            st.session_state.free_used_this_session = True
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
