# StripeToQBO — Konwertuj Stripe CSV → QuickBooks Online

MVP zbudowany dla bootstrappera. Jeden plik Pythona, zero bazy danych, zero OAuth.

## 🚀 Jak wystartować (3 kroki)

### 1. Wdróż aplikację Streamlit (ZA DARMO)

1. Załóż konto na [GitHub.com](https://github.com) (jeśli nie masz)
2. Stwórz nowe repozytorium, wrzuć do niego pliki:
   - `app.py`
   - `requirements.txt`
   - `.streamlit/secrets.toml`
3. Wejdź na [share.streamlit.io](https://share.streamlit.io)
4. Kliknij **"New app"** → wybierz repozytorium → plik `app.py` → **Deploy**
5. Po 60 sekundach aplikacja jest online. Skopiuj URL.

### 2. Wdróż landing page (ZA DARMO)

1. Wejdź na [Netlify.com](https://netlify.com) (darmowe konto)
2. Przeciągnij plik `index.html` do okna przeglądarki
3. Strona jest online. Skopiuj URL.
4. **WAŻNE:** W pliku `index.html` zamień:
   - `YOUR_STREAMLIT_URL_HERE` → URL aplikacji Streamlit
   - `PASTE_SOLO_LINK` → Twój Stripe Payment Link dla planu Solo
   - `PASTE_PRO_LINK` → Twój Stripe Payment Link dla planu Pro

### 3. Podłącz Stripe (przyjmuj płatności)

1. Załóż konto na [Stripe.com](https://stripe.com)
2. W panelu Stripe: **Produkty** → **Utwórz produkt**
   - Plan Solo: $15/miesiąc
   - Plan Pro: $29/miesiąc
3. Dla każdego produktu: **Utwórz link płatności**
4. Skopiuj linki i wklej je w `index.html` oraz w linki `st.link_button` w `app.py`

### Koszt infrastruktury: ~0 zł / miesiąc

- Streamlit Cloud: darmowy (aplikacje publiczne)
- Netlify: darmowy
- Stripe: tylko opłaty od transakcji (2.9% + 1.20 zł)

---

## 🔧 Konfiguracja dostępu (opcjonalna)

Jeśli chcesz zablokować aplikację hasłem:

1. W panelu Streamlit Cloud przejdź do **Settings → Secrets**
2. Dodaj:
```

ACCESS_CODE = "twoje-haslo"

```
3. Zrestartuj aplikację.

Jeśli NIE dodasz ACCESS_CODE — aplikacja jest otwarta dla wszystkich (tryb darmowej pierwszej konwersji).

---

## 📦 Co jest w pudełku

| Plik | Zawartość |
|------|-----------|
| `app.py` | Główna aplikacja Streamlit |
| `requirements.txt` | Zależności Pythona |
| `index.html` | Landing page (gotowy do wrzucenia na Netlify) |
| `marketing-copy.md` | Gotowe teksty do Reddit, LinkedIn, maili — kopiuj-wklej |
| `.streamlit/secrets.toml` | Szablon konfiguracji |

---

## 🧠 Dla mózgu z ADHD

- **Nie dodawaj nowych funkcji**, dopóki pierwszy płacący klient o nie nie poprosi.
- **Nie zmieniaj technologii.** Streamlit działa. HTML na Netlify działa. Stripe działa. Nie dotykaj tego.
- **Po deployu — wyślij link do 3 księgowych.** Nie do 50. Do 3.
- Kod jest celowo w JEDNYM pliku (`app.py`). To feature, nie bug.

---

Gotowe? Pierwszy klient czeka.
