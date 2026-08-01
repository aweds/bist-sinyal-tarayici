# BIST Sinyal Tarayıcı

Kural tabanlı, tamamen şeffaf bir teknik analiz **sinyal** aracı — BIST (Borsa
Istanbul) hisseleri için AL / SAT / BEKLE sinyalleri üretir. **Otomatik emir
göndermez** — emirleri siz aracı kurum uygulamanızdan manuel olarak
verirsiniz.

> ⚠️ Bu araç yatırım tavsiyesi değildir. Sinyaller geçmiş fiyat ve hacim
> verisine dayalı basit kurallardan üretilir. Kayıp riskini artırabilir.
> Kendi araştırmanızı yapın, gerekirse lisanslı bir yatırım danışmanına
> danışın.

## Nasıl çalışır?

- Veri kaynağı: [Yahoo Finance](https://finance.yahoo.com) (`yfinance`
  kütüphanesi ile). BIST hisseleri `.IS` son eki ile çekilir (örn.
  `THYAO.IS`, `GARAN.IS`).
- Sinyal motoru 5 bileşeni birleştirip -100 ile +100 arası bir **skor**
  üretir:
  1. **Trend** — Fiyatın SMA50 / SMA200'e göre konumu
  2. **Momentum** — RSI(14) aşırı alım/satım bölgeleri
  3. **MACD** — Sinyal çizgisi kesişimi ve histogram yönü
  4. **Bollinger Bantları** — Ortalamaya dönüş sinyalleri
  5. **Hacim teyidi** — Ortalama hacmin üzerindeki hareketler
- Her sinyal, hangi kuralların tetiklendiğini gösteren **gerekçe listesi**
  ile birlikte gelir — kara kutu değildir.
- Basit bir backtest modülü, stratejinin geçmişte "al-tut" stratejisine
  karşı nasıl performans gösterdiğini simüle eder (komisyon/kayma dahil
  değildir).

## Dosya yapısı

```
bist_signal_app/
├── app.py            # Streamlit arayüzü (ana dosya)
├── strategy.py        # Sinyal skorlama + backtest mantığı
├── indicators.py       # SMA/EMA/RSI/MACD/Bollinger/ATR hesaplamaları
├── bist_tickers.py     # BIST30/BIST100 hisse listesi (Yahoo ticker formatı)
├── requirements.txt
└── README.md
```

## Yerel (local) çalıştırma

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Tarayıcıda otomatik olarak `http://localhost:8501` açılacaktır.

## Streamlit Community Cloud'a deploy etme (ücretsiz)

1. Bu klasörü bir GitHub reposuna yükleyin (public veya private).
2. [share.streamlit.io](https://share.streamlit.io) adresine gidip GitHub
   hesabınızla giriş yapın.
3. "New app" → reponuzu seçin → main file olarak `app.py` seçin → Deploy.
4. Birkaç dakika içinde `https://<uygulama-adiniz>.streamlit.app` adresinde
   canlıya alınır. Bu link mobil tarayıcıdan da açılır ve Android/iOS'ta
   "Ana ekrana ekle" ile bir uygulama gibi kullanılabilir (PWA benzeri).

## Bilinen sınırlamalar

- **Veri gecikmesi:** Yahoo Finance BIST verisi gerçek zamanlı olmayabilir,
  birkaç dakika gecikmeli olabilir ve bazı ilişkisiz semboller için veri
  eksik/hatalı olabilir. Emir vermeden önce mutlaka aracı kurum
  ekranınızdan teyit edin.
- **Günlük (daily) veri kullanılıyor:** Sistem gün içi (intraday) değil,
  günlük kapanış barları üzerinden çalışır — "günlük işlem" (daily
  rebalancing / swing) tarzına uygundur, dakikalık scalping için değildir.
  Gün içi barlarla çalışmak isterseniz `fetch_history` fonksiyonundaki
  `interval` parametresi `"15m"`/`"1h"` olarak değiştirilebilir (yfinance'in
  gün içi veri için 60 günlük geçmiş sınırı vardır).
- **Backtest basitleştirilmiştir:** Komisyon, kayma (slippage), gap riski
  ve likidite kısıtları modellenmemiştir. Gerçek sonuçlar daha düşük
  olacaktır.
- **Emir gönderme yok:** Bu sürüm sadece sinyal üretir. Otomatik emir
  gönderimi için bir aracı kurumun algoritmik işlem API'sine (örn.
  AlgoLab/İş Yatırım, Midas, Denizbank Yatırım gibi Türkiye'de algo-trading
  destekleyen kurumlar) ihtiyaç vardır — bu, ayrı bir entegrasyon adımıdır
  ve önemli ek risk taşır.

## Sıradaki adımlar (Android)

Streamlit uygulaması zaten mobil tarayıcıda responsive çalışır. Android
tarafı için iki pratik yol var:

1. **Hızlı yol — PWA / WebView sarmalayıcı:** Deploy edilen Streamlit
   linkini basit bir Android WebView içine gömüp Play Store'a
   yayınlayabilir ya da kullanıcıların tarayıcıdan "Ana ekrana ekle"
   yapmasını sağlayabilirsiniz. Ek geliştirme gerektirmez.
2. **Native yol:** Sinyal motorunu (`strategy.py`, `indicators.py`) bir
   backend API'ye (FastAPI) taşıyıp, Kotlin veya Flutter ile ayrı bir
   native arayüz geliştirmek — daha fazla emek ister ama push bildirim,
   arka planda tarama gibi özellikler ekleyebilirsiniz.

İsterseniz bir sonraki adımda bunlardan birini birlikte kuralım.
