"""Long-tail candidate discovery. Scores express research priority, never volume/KD."""
from dataclasses import dataclass, field
import re
import unicodedata

MONTHS = 'january february march april may june july august september october november december'.split()
TR_MONTHS = 'ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık'.split()
FORMATS = {'pdf', 'jpg', 'jpeg', 'png', 'a4', 'letter', 'landscape', 'portrait', 'yatay', 'dikey'}


def normalize(text):
    text = unicodedata.normalize('NFKC', str(text)).casefold()
    return ' '.join(re.findall(r'[^\W_]+', text, re.UNICODE))


def words(text):
    return normalize(text).split()


def relevant(query, seeds):
    q = set(words(query))
    for seed in seeds:
        anchor = set(words(seed)) - set(re.findall(r'\b20\d{2}\b', seed)) - {'free', 'printable', 'ücretsiz'}
        if anchor and anchor <= q:
            return True
    return False


def classify(query):
    tokens = set(words(query))
    if tokens & {'how', 'why', 'what', 'when', 'nasıl', 'neden', 'nedir', 'ne'}:
        return 'Bilgi / soru'
    if tokens & {'vs', 'versus', 'best', 'alternative', 'alternatives', 'karşılaştırma'}:
        return 'Karşılaştırma'
    if tokens & {'download', 'printable', 'pdf', 'template', 'free', 'indir', 'yazdırılabilir', 'ücretsiz', 'şablon'}:
        return 'İndir / kullan'
    return 'Genel araştırma'


def facets(query):
    tokens = set(words(query))
    labels = []
    if tokens & set(MONTHS + TR_MONTHS): labels.append('Ay')
    if re.search(r'\b20\d{2}\b', query): labels.append('Yıl')
    if tokens & FORMATS: labels.append('Format / baskı')
    if tokens & {'school', 'teacher', 'student', 'family', 'kids', 'okul', 'öğretmen', 'aile'}: labels.append('Kullanım amacı')
    if tokens & {'blank', 'notes', 'weekly', 'monthly', 'yearly', 'boş', 'haftalık', 'aylık', 'yıllık'}: labels.append('Düzen')
    return ', '.join(labels) or 'Genel'


def cluster(query):
    # Preserve month/year and intent; group paper/file variants for review.
    return ' '.join(t for t in words(query) if t not in FORMATS)


def generate(seeds, profile='Takvim / printable', language='English', years=()):
    tr = language == 'Türkçe'
    generic = (['ücretsiz', 'indir', 'şablon', 'nasıl kullanılır', 'alternatifleri'] if tr else
               ['free', 'template', 'download', 'how to use', 'alternatives'])
    modifiers = generic
    if profile == 'Takvim / printable':
        modifiers = (['ücretsiz yazdırılabilir', 'pdf indir', 'a4', 'boş şablon', 'not alanlı', 'hafta pazartesi başlayan', 'okul için'] if tr else
                     ['free printable', 'pdf download', 'a4', 'blank template', 'with notes', 'monday start', 'sunday start', 'landscape', 'for school', 'with holidays'])
    out = []
    for seed in seeds:
        seed = seed.strip()
        if not seed: continue
        bases = [seed]
        if years and not re.search(r'\b20\d{2}\b', seed):
            bases += [f'{seed} {year}' for year in years]
        for base in bases:
            out.append(base)
            for modifier in modifiers:
                if not set(words(modifier)) <= set(words(base)):
                    out.append(f'{base} {modifier}')
            if profile == 'Takvim / printable' and not set(words(base)) & set(MONTHS + TR_MONTHS):
                for month in (TR_MONTHS if tr else MONTHS):
                    monthly = f'{month} {base}'
                    out += [monthly, f'{monthly} pdf', f'{monthly} {"ücretsiz yazdırılabilir" if tr else "free printable"}']
    return list(dict.fromkeys(out))


@dataclass
class Candidate:
    query: str
    sources: set = field(default_factory=set)
    seeds: set = field(default_factory=set)
    evidence: list = field(default_factory=list)


def build_rows(seeds, generated=(), manual=(), observations=(), min_words=1,
               only_relevant=False, include='', exclude=''):
    merged = {}
    def add(query, source, seed='', evidence=None):
        query = ' '.join(str(query).split())
        key = normalize(query)
        if not key: return
        item = merged.setdefault(key, Candidate(query))
        item.sources.add(source)
        if seed: item.seeds.add(seed)
        if evidence is not None and evidence not in item.evidence: item.evidence.append(evidence)
    for query in generated: add(query, 'Üretilen aday')
    for query in manual: add(query, 'Kullanıcı listesi')
    for obs in observations:
        for part in ('top', 'rising'):
            for item in obs['data'].get(part, []):
                if not item.get('query'): continue
                value = item.get('formatted_value') or str(item.get('value', ''))
                add(item['query'], f'Trends {part.title()}', obs['seed'],
                    f"{obs['seed']} | {part}: {value} | {obs.get('fetched_at', '')}" +
                    (' | eski kayıt' if obs.get('stale') else ''))
    includes = [normalize(t) for t in include.split(',') if normalize(t)]
    excludes = [normalize(t) for t in exclude.split(',') if normalize(t)]
    rows = []
    for item in merged.values():
        q = normalize(item.query)
        if len(words(q)) < min_words: continue
        if only_relevant and not relevant(q, seeds): continue
        if includes and not all(t in q for t in includes): continue
        if any(t in q for t in excludes): continue
        top, rising = 'Trends Top' in item.sources, 'Trends Rising' in item.sources
        specificity = min(max(len(words(q)) - 2, 0) * 4, 20)
        intent = classify(q)
        score = (30 if top else 0) + (30 if rising else 0) + specificity + (10 if intent != 'Genel araştırma' else 0) + min(len(item.seeds) * 5, 10)
        rows.append({'Sorgu': item.query, 'Öncelik': score,
                     'Kanıt': 'Trends gözlemi' if top or rising else 'Doğrulanmamış aday',
                     'Niyet': intent, 'Özellik': facets(q), 'Küme': cluster(q),
                     'Kelime': len(words(q)), 'Kaynak': ', '.join(sorted(item.sources)),
                     'Bulunduğu kökler': ', '.join(sorted(item.seeds)),
                     'Trends kanıtı': '\n'.join(item.evidence)})
    return sorted(rows, key=lambda r: (-r['Öncelik'], -r['Kelime'], r['Sorgu']))
