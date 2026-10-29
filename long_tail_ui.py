"""Streamlit long-tail workbench; network calls only on explicit research clicks."""
from datetime import datetime
import json
import pandas as pd
import streamlit as st
from long_tail import build_rows, generate, relevant, normalize
from related_queries import explore_url


def render_long_tail(seeds, geo, timeframe, service):
    st.subheader('Uzun Kuyruk Araştırması')
    st.caption('Aday üret → gerçek Top/Rising ile zenginleştir → niyet ve kümeleri incele → araştırılacak sorguyu seç.')
    if not seeds:
        st.info('Soldan en az bir ana kelime girin.')
        return
    c1, c2, c3 = st.columns(3)
    profile = c1.selectbox('Araştırma profili', ['Takvim / printable', 'Genel'],
                           index=0 if any('calendar' in s.casefold() or 'takvim' in s.casefold() for s in seeds) else 1)
    language = c2.selectbox('Aday dili', ['English', 'Türkçe'])
    year_default = [datetime.now().year + 1, datetime.now().year + 2] if profile == 'Takvim / printable' else []
    years = c3.multiselect('Yıl genişletmesi', list(range(2020, 2041)), default=year_default)
    manual_text = st.text_area('Kendi sorgularını ekle (her satıra bir sorgu)',
                               help='GSC, Trends veya kendi araştırmandan sorguları yapıştırabilirsin. Kullanıcı listesi Trends kanıtı sayılmaz.')
    generated = generate(seeds, profile, language, years)
    state_key = json.dumps([seeds, geo, timeframe])
    queued = st.session_state.setdefault('long_tail_roots', {})
    roots = queued.setdefault(state_key, list(seeds))
    observations = []
    for seed in roots:
        cached = service.peek(seed, geo, timeframe)
        if cached and cached.data:
            observations.append({'seed': seed, 'data': cached.data,
                                 'fetched_at': datetime.fromtimestamp(cached.fetched_at).astimezone().isoformat(timespec='seconds'),
                                 'stale': cached.stale})
    all_rows = build_rows(seeds, generated, manual_text.splitlines(), observations)
    candidates = list(dict.fromkeys(roots + [r['Sorgu'] for r in all_rows
                    if r['Kanıt'] == 'Trends gözlemi' and relevant(r['Sorgu'], seeds)]))
    with st.container(border=True):
        st.markdown('**Bir sonraki araştırma**')
        st.caption('Bir tıklama bir kökü araştırır. Filtrelemek ve CSV indirmek yeni Google isteği göndermez. Aynı ülke/tarih için kaydedilmiş Top/Rising verisi otomatik eklenir.')
        next_seed = st.selectbox('Top/Rising getirilecek sorgu', candidates)
        custom_root = st.text_input('Veya araştırılacak farklı bir sorgu', key='lt_custom_root')
        selected = custom_root.strip() or next_seed
        st.link_button('Seçili sorguyu Google Trends’te aç', explore_url(selected, geo, timeframe))
        if st.button('Seçili sorgunun Top / Rising verisini getir', type='primary'):
            with st.spinner('Google Trends Explore verisi alınıyor…'):
                result = service.get(selected, geo, timeframe)
            if result.message: st.warning(result.message)
            if result.retry_after: st.info(f'Yeni canlı istek için yaklaşık {result.retry_after} saniye bekleyin.')
            if result.data is not None:
                if selected not in roots: roots.append(selected)
                # Read again without triggering a second network call.
                observations = [o for o in observations if o['seed'] != selected]
                observations.append({'seed': selected, 'data': result.data,
                                     'fetched_at': datetime.fromtimestamp(result.fetched_at).astimezone().isoformat(timespec='seconds'),
                                     'stale': result.stale})
                all_rows = build_rows(seeds, generated, manual_text.splitlines(), observations)
                st.success('Top/Rising kayıtları araştırmaya eklendi.' if not result.stale else 'Önceki kayıtlar tarih etiketiyle eklendi.')
    if any(o['stale'] for o in observations):
        st.warning('Bazı Trends gözlemleri eski kayıtlardır; alınma tarihleri kanıt sütununda yer alır.')
    m1, m2, m3 = st.columns(3)
    m1.metric('Tekil sorgu', len(all_rows))
    m2.metric('Trends’te gözlenen', sum(r['Kanıt'] == 'Trends gözlemi' for r in all_rows))
    m3.metric('Verisi bulunan kök', len(observations))
    with st.expander('Öncelik puanı ve veri nasıl yorumlanmalı?'):
        st.write('Bu puan araştırma sırasını belirleyen bir kuraldır; arama hacmi, sıralama olasılığı veya rekabet ölçümü değildir. Üretilen adayların talebi doğrulanmamıştır. Uzun sorgu her zaman düşük rekabet demek değildir.')
        st.write('Top kaydı +30, Rising kaydı +30, 2 kelime üstündeki her kelime +4 (en çok 20), belirgin niyet +10, gözlendiği her kök +5 (en çok 10). En yüksek puan 100.')
        st.write('Top ve Rising değerleri kök sorgu ve tarih bağlamıyla saklanır; farklı köklerin değerleri tek bir arama hacmine çevrilmez. Aynı kümedeki PDF/A4 gibi varyantları ayrı sayfa açmadan önce birlikte değerlendirin. Kümeleme sözcük tabanlı bir ön elemedir.')
        st.markdown('[Google: Related searches açıklaması](https://support.google.com/trends/answer/4355000?hl=en)')
    c1, c2, c3 = st.columns(3)
    minimum = c1.number_input('En az kelime', min_value=1, max_value=20, value=3)
    evidence = c2.selectbox('Kanıt filtresi', ['Tümü', 'Trends gözlemi', 'Doğrulanmamış aday'])
    intent = c3.selectbox('Niyet filtresi', ['Tümü', 'İndir / kullan', 'Bilgi / soru', 'Karşılaştırma', 'Genel araştırma'])
    c1, c2 = st.columns(2)
    include = c1.text_input('İçersin (virgülle; tümü)', key='lt_include')
    exclude = c2.text_input('Hariç tut (virgülle; herhangi biri)', key='lt_exclude')
    only_relevant = st.checkbox('Ana kelime sözcüklerini koruyan sorgular', value=False)
    rows = build_rows(seeds, generated, manual_text.splitlines(), observations,
                      int(minimum), only_relevant, include, exclude)
    rows = [r for r in rows if (evidence == 'Tümü' or r['Kanıt'] == evidence)
            and (intent == 'Tümü' or r['Niyet'] == intent)]
    st.caption(f'{len(rows)} / {len(all_rows)} kayıt gösteriliyor. Sonuç sayısı sınırı yok; filtreler değiştirilebilir.')
    if rows:
        frame = pd.DataFrame(rows)
        st.dataframe(frame, use_container_width=True, hide_index=True, height=600)
        groups = frame.groupby(['Küme', 'Niyet'], as_index=False).agg(
            Sorgular=('Sorgu', lambda values: ' | '.join(values)), Adet=('Sorgu', 'size'))
        with st.expander('İçerik kümeleri'):
            st.dataframe(groups, use_container_width=True, hide_index=True)
        st.download_button('Görünen sorguları CSV indir', frame.to_csv(index=False).encode('utf-8-sig'),
                           'long-tail-filtered.csv', 'text/csv')
    else:
        st.info('Bu filtrelere uyan sorgu yok. Minimum kelime sayısını azaltabilir veya filtreleri değiştirebilirsin.')
    st.download_button('Tüm araştırmayı JSON indir', json.dumps({
        'seeds': seeds, 'geo': geo, 'timeframe': timeframe, 'profile': profile,
        'language': language, 'years': years, 'observations': observations, 'candidates': all_rows,
    }, ensure_ascii=False, indent=2).encode(), 'long-tail-research.json', 'application/json')
    if all_rows:
        st.download_button('Tüm sorguları CSV indir', pd.DataFrame(all_rows).to_csv(index=False).encode('utf-8-sig'),
                           'long-tail-all.csv', 'text/csv')
