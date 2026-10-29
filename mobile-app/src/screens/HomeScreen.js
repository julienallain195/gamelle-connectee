import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, Image, StyleSheet } from 'react-native';
import { collection, query, orderBy, limit, onSnapshot, getDocs } from 'firebase/firestore';
import { ref, getDownloadURL } from 'firebase/storage';
import { db, storage } from '../services/firebase';

// Échelle de la jauge : score = texture*0.7 + luminosité*0.3 (voir detector.py).
// On considère que 2x le seuil "vide" = gamelle pleine à 100 %.
const EMPTY_THRESHOLD = 35;
const FULL_SCORE = EMPTY_THRESHOLD * 2;

export default function HomeScreen() {
  const [events, setEvents] = useState([]);
  const [lastPhotoUrl, setLastPhotoUrl] = useState(null);
  const [weekStats, setWeekStats] = useState([]); // [{date, fullRatio}]

  useEffect(() => {
    // Historique des relevés + dernier état
    const q = query(collection(db, 'events'), orderBy('timestamp', 'desc'), limit(20));
    const unsub = onSnapshot(q, (snap) => {
      const docs = snap.docs.map(d => ({ id: d.id, ...d.data() }));
      // Les relevés "vue masquée" n'ont pas d'état exploitable
      setEvents(docs.filter(e => !e.occluded));
      // Vignette : photo du dernier relevé qui en a une
      const withPhoto = docs.find(e => e.photoPath);
      if (withPhoto?.photoPath) {
        getDownloadURL(ref(storage, withPhoto.photoPath))
          .then(setLastPhotoUrl)
          .catch(() => setLastPhotoUrl(null));
      }
    });
    return () => unsub();
  }, []);

  useEffect(() => {
    // Courbe des 7 derniers jours (remplissage moyen par jour)
    const q = query(collection(db, 'dailyStats'), orderBy('date', 'desc'), limit(7));
    return onSnapshot(q, (snap) => {
      const stats = snap.docs.map(d => {
        const data = d.data();
        const total = (data.fullChecks || 0) + (data.emptyChecks || 0);
        return {
          date: data.date,
          fullRatio: total > 0 ? (data.fullChecks || 0) / total : null,
          catSightings: data.catSightings || 0,
        };
      });
      setWeekStats(stats.reverse()); // chronologique gauche → droite
    });
  }, []);

  const last = events[0];
  const gaugePercent = last
    ? Math.min(Math.max(last.fillScore / FULL_SCORE, 0), 1)
    : 0;

  return (
    <FlatList
      style={styles.container}
      data={events.slice(1)}
      keyExtractor={item => item.id}
      ListHeaderComponent={
        <View>
          <Text style={[styles.status, last?.bowlEmpty ? styles.statusEmpty : styles.statusFull]}>
            {last ? (last.bowlEmpty ? '🚨 Gamelle VIDE' : '✅ Gamelle pleine') : '⏳ En attente de relevé…'}
          </Text>

          {/* Vignette dernière photo + jauge de remplissage */}
          <View style={styles.card}>
            {lastPhotoUrl ? (
              <Image source={{ uri: lastPhotoUrl }} style={styles.thumbnail} />
            ) : (
              <View style={[styles.thumbnail, styles.thumbnailEmpty]}>
                <Text style={styles.thumbnailText}>Pas encore de photo</Text>
              </View>
            )}
            <View style={styles.gaugeBlock}>
              <Text style={styles.gaugeTitle}>Niveau estimé</Text>
              <View style={styles.gaugeBackground}>
                <View style={[styles.gaugeFill, { flex: gaugePercent }, gaugePercent <= 0 && styles.hidden]} />
                <View style={[styles.gaugeRest, { flex: 1 - gaugePercent }]} />
              </View>
              <Text style={styles.gaugeValue}>
                {last ? `score ${last.fillScore}` : '—'} (seuil vide : {EMPTY_THRESHOLD})
              </Text>
              {last?.timestamp && (
                <Text style={styles.lastCheck}>
                  Dernier relevé : {last.timestamp.toDate().toLocaleString('fr-FR')}
                </Text>
              )}
            </View>
          </View>

          {/* Courbe de la semaine */}
          {weekStats.length > 0 && (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Gamelle pleine au cours de la semaine</Text>
              <View style={styles.chart}>
                {weekStats.map(s => (
                  <View key={s.date} style={styles.chartColumn}>
                    <View style={styles.chartBarArea}>
                      <View
                        style={[
                          styles.chartBar,
                          { height: `${Math.round((s.fullRatio ?? 0) * 100)}%` },
                        ]}
                      />
                    </View>
                    <Text style={styles.chartLabel}>{s.date.slice(8)}</Text>
                  </View>
                ))}
              </View>
              <Text style={styles.chartHint}>Hauteur = % du temps où la gamelle était pleine</Text>
            </View>
          )}

          <Text style={styles.sectionTitle}>Historique des derniers relevés</Text>
        </View>
      }
      renderItem={({ item }) => (
        <View style={styles.row}>
          <Text style={styles.rowIcon}>{item.bowlEmpty ? '🚨' : '🍽️'}</Text>
          <Text style={styles.rowText}>
            {item.bowlEmpty ? 'Gamelle vide' : 'Gamelle pleine'}
            {item.catSeen ? ' · 🐱 chat vu' : ''} — {item.timestamp?.toDate().toLocaleString('fr-FR')}
          </Text>
        </View>
      )}
      ListEmptyComponent={
        <Text style={styles.emptyList}>Aucun relevé pour l'instant</Text>
      }
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f5f5f5' },
  status: { fontSize: 24, fontWeight: 'bold', marginBottom: 12, textAlign: 'center' },
  statusEmpty: { color: '#c0392b' },
  statusFull: { color: '#27ae60' },
  card: {
    backgroundColor: '#fff', borderRadius: 10, padding: 12,
    marginBottom: 12, flexDirection: 'row',
  },
  thumbnail: {
    width: 110, height: 82, borderRadius: 8, backgroundColor: '#ddd',
  },
  thumbnailEmpty: { alignItems: 'center', justifyContent: 'center' },
  thumbnailText: { color: '#999', fontSize: 11 },
  gaugeBlock: { flex: 1, marginLeft: 12, justifyContent: 'center' },
  gaugeTitle: { fontSize: 13, fontWeight: '600', color: '#555' },
  gaugeBackground: {
    flexDirection: 'row', height: 14, borderRadius: 7,
    backgroundColor: '#eee', overflow: 'hidden', marginVertical: 6,
  },
  gaugeFill: { backgroundColor: '#27ae60' },
  gaugeRest: { backgroundColor: 'transparent' },
  hidden: { display: 'none' },
  gaugeValue: { fontSize: 12, color: '#888' },
  lastCheck: { fontSize: 12, color: '#888', marginTop: 2 },
  cardTitle: { fontSize: 13, fontWeight: '600', color: '#555', marginBottom: 8 },
  chart: { flexDirection: 'row', height: 80 },
  chartColumn: { flex: 1, alignItems: 'center' },
  chartBarArea: { flex: 1, width: '70%', justifyContent: 'flex-end' },
  chartBar: { backgroundColor: '#27ae60', borderRadius: 3 },
  chartLabel: { fontSize: 10, color: '#888', marginTop: 4 },
  chartHint: { fontSize: 10, color: '#aaa', marginTop: 6 },
  sectionTitle: { fontSize: 13, color: '#888', textTransform: 'uppercase', marginBottom: 6 },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  rowIcon: { marginRight: 8 },
  rowText: { fontSize: 14 },
  emptyList: { textAlign: 'center', color: '#888', marginTop: 32 },
});
