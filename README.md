# Google Trends Desktop App (macOS)

Gelişmiş arayüzlü, Mac'te çalışan Google Trends aracı.

## Kurulum (Mac)

```bash
# 1. Klasöre gir
cd google-trends-app

# 2. Sanal ortam oluştur (önerilir)
python3 -m venv venv
source venv/bin/activate

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. Çalıştır
streamlit run dashboard.py   # Fresh Calendars News Radar (önerilen)
# veya
streamlit run app.py         # tüm Trends modları
```

Tarayıcı otomatik açılır (genelde http://localhost:8501).

### Streamlit Community Cloud (bedava, RSS modu)

Public deploy: see [DEPLOY_STREAMLIT.md](DEPLOY_STREAMLIT.md). Main file: **`dashboard.py`**.

```bash
export FC_CLOUD=1   # local parity with Cloud
streamlit run dashboard.py --server.port 8502
```

## Özellikler

- **FC News Radar (`dashboard.py`)** — US autocomplete long-tail keşfi (seed + boşluk + **a–z** + how/what/when…) + Trends + slug gap
- **Opportunity Radar** — aynı motor, `app.py` içinde kısa görünüm
- **Interest Over Time** — tarih aralığı seçilebilir, grafik
- **Related Queries** — top + rising
- **Trending Now** — ülke bazlı anlık trendler (RSS, hızlı)
- **Interest by Region**
- Geo (ülke) seçimi
- Tarih aralığı seçimi (preset + özel)
- CSV / JSON export
- Çoklu keyword karşılaştırma

## Notlar

- Interest / Related için `trendspy` kullanılıyor (stabil).
- Trending Now için `trendspyg` RSS (Chrome gerekmez, hızlı).
- Google rate limit uygulayabilir; çok sık istekte kısa süre bekle.

## Related Queries erişimi

Related Queries, `trendspy` embed çağrısı yerine `trendspyg` ile Chrome üzerinden
Google Trends Explore verisini alır. Mac'te Google Chrome kurulu olmalıdır.
Seçilen ülke ve tarih aralığı uygulanır; bu mod ilk keyword'ü kullanır.

- Günlük/haftalık aralıklar 24 saat, `now` aralıkları 1 saat önbellekten sunulur.
- Kayıtlar proje içindeki `.cache/related.sqlite3` dosyasında saklanır.
- Farklı canlı sorgular arasında en az 30 saniye beklenir.
- Google kota/erişim sınırı döndürürse yeni sorgular 30 dakika durdurulur.
  Bu süre Google'ın kısıtının kesin kalkacağı anlamına gelmez.
- Diğer erişim hatalarında 2 dakika beklenir. Eski kayıt varsa alınma tarihiyle
  gösterilir; boş widget yanıtı başarılı ve kesin bir “sonuç yok” verisi sayılmaz.
- Google Trends bağlantısı aynı keyword, ülke ve tarih aralığını açar.
- CSV indirme ve diğer arayüz yenilemeleri mevcut sonucu kaybettirmez.

## FC News Radar — akış (A→Z)

1. **Motor** — US seed paketi seçilir (election, holiday, …).
2. **Keşif** — `suggestqueries.google.com`: seed, `seed␠`, `seed␠a…z`, `how/what/when… seed`.
3. **Filtre** — Seed ile alakalı, min kelime sayısı, generic spam elenir.
4. **Trends** — Trending Now RSS + (varsa) Related cache + top-5 long-tail için 7g interest.
5. **Skor** — Autocomplete relevance, specificity (county/deadline/…), uzun kuyruk bonusu, tier.
6. **Gap** — `freshcalendars.com/news/post-sitemap.xml` slug eşleşmesi → Skip veya Write.
7. **Dashboard** — Catch now kartları, tablo, CSV/JSON.

Doğrulama: `venv/bin/python -m unittest discover -s tests -v`

## Uzun Kuyruk Araştırması

Soldaki mod listesinden **Uzun Kuyruk Araştırması** seçilir. Aday üretimi internet
isteği yapmaz. Birden çok kök kelime, Türkçe/İngilizce, genel veya takvim profili,
yıl ve ay genişletmeleri, kullanım amacı ve baskı özellikleri desteklenir.
Mevcut yılı/ayı olan köklere ikinci bir yıl/ay eklenmez.

**Seçili sorgunun Top / Rising verisini getir** düğmesi bir kökü araştırır.
Kaydedilmiş aynı ülke/tarih sonuçları otomatik birleştirilir. Gözlenen sorgulardan
birini sonraki kök seçerek araştırmayı derinleştirebilirsiniz. Kota beklemesi
Related Queries modu ile paylaşılır. Filtreleme ve indirme Google isteği göndermez.

- Gerçek Trends gözlemleri, kullanıcı listesi ve üretilen adaylar ayrı etiketlenir.
- Aynı sorgunun farklı köklerdeki Top/Rising kanıtları ve alınma tarihleri korunur.
- Öncelik puanı yalnızca açıklanan kurallarla araştırma sırasını belirler;
  hacim, SEO zorluğu veya düşük rekabet iddiası değildir.
- Kelime, kanıt, niyet, içerme/hariç tutma ve sözcük ilgisi filtreleri bulunur.
  Varsayılan minimum 3 kelimedir; tümünü görmek için 1 yapılabilir.
- Sözcük tabanlı kümeler PDF/A4 gibi format varyantlarını birlikte incelemeye
  yardımcı olur; ay/yıl korunur. Kümeler otomatik sayfa açma kararı değildir.
- Görünen veya tüm kayıtlar CSV; filtreler, kökler ve gözlemler JSON indirilebilir.
  Sonuç listesine satır sınırı uygulanmaz.
