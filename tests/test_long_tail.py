import unittest
from long_tail import build_rows, generate, cluster, relevant, classify


class LongTailTests(unittest.TestCase):
    def test_generation_keeps_existing_year_and_month(self):
        rows = generate(['january 2027 calendar'], years=[2028])
        self.assertFalse(any('2028' in q or 'february' in q for q in rows))
        self.assertTrue(any('pdf' in q for q in rows))
        expanded = generate(['calendar'], years=[2027, 2028])
        self.assertIn('january calendar 2028 free printable', expanded)
        self.assertEqual(len(expanded), len(set(expanded)))

    def test_dedup_keeps_independent_evidence_values(self):
        obs = [dict(seed='calendar', fetched_at='2026-10-20', data={
            'top': [dict(query='Free Printable Calendar PDF', value=90)], 'rising': []}),
            dict(seed='printable calendar', fetched_at='2026-10-19', stale=True, data={
            'top': [], 'rising': [dict(query='free printable calendar pdf', value=5000, formatted_value='Breakout')]})]
        rows = build_rows(['calendar'], ['free printable calendar pdf'], observations=obs)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['Kanıt'], 'Trends gözlemi')
        self.assertIn('top: 90', row['Trends kanıtı'])
        self.assertIn('Breakout', row['Trends kanıtı'])
        self.assertIn('eski kayıt', row['Trends kanıtı'])
        self.assertLessEqual(row['Öncelik'], 100)

    def test_unverified_candidates_and_manual_list_are_not_observations(self):
        rows = build_rows(['calendar'], ['free calendar pdf'], ['calendar with notes'])
        self.assertTrue(all(row['Kanıt'] == 'Doğrulanmamış aday' for row in rows))
        self.assertTrue(all(not row['Trends kanıtı'] for row in rows))

    def test_filtering_and_relevance(self):
        rows = build_rows(['2027 calendar'], ['free calendar pdf', 'free calendar jpg', 'football results'],
                          min_words=3, only_relevant=True, include='free,calendar', exclude='jpg')
        self.assertEqual([r['Sorgu'] for r in rows], ['free calendar pdf'])
        self.assertFalse(relevant('calendars football', ['calendar']))
        self.assertTrue(relevant('free 2028 calendar', ['2027 calendar']))

    def test_cluster_preserves_year_month_but_groups_file_variants(self):
        self.assertEqual(cluster('january calendar 2027 pdf a4'), cluster('january calendar 2027 jpg'))
        self.assertNotEqual(cluster('january calendar 2027'), cluster('february calendar 2027'))
        self.assertNotEqual(cluster('january calendar 2027'), cluster('january calendar 2028'))

    def test_turkish_and_intent(self):
        self.assertEqual(classify('takvim nasıl kullanılır'), 'Bilgi / soru')
        self.assertEqual(classify('ücretsiz takvim indir'), 'İndir / kullan')
        self.assertIn('ocak takvim 2027 pdf', generate(['takvim'], language='Türkçe', years=[2027]))

    def test_all_rows_kept(self):
        queries = [f'calendar printable template {i}' for i in range(230)]
        self.assertEqual(len(build_rows(['calendar'], queries)), 230)


if __name__ == '__main__':
    unittest.main()
