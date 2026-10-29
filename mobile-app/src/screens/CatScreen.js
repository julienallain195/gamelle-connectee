import React, { useEffect, useState } from 'react';
import { View, ScrollView, Text, StyleSheet, RefreshControl } from 'react-native';
import { collection, query, orderBy, limit, getDocs } from 'firebase/firestore';
import { db } from '../services/firebase';

const ALERT_HOURS = 12; // alerte si le chat n'a pas été vu depuis 12h

function formatDelay(ms) {
  const hours = Math.floor(ms / 3600000);
  if (hours < 1) {
    const minutes = Math.max(1, Math.floor(ms / 60000));
    return `il y a ${minutes} min`;
  }
  if (hours < 48) return `il y a ${hours} h`;
  return `il y a ${Math.floor(hours / 24)} j`;
}

export default function CatScreen() {
  const [lastSeen, setLastSeen] = useState(null); // Date | null
  const [hourHistogram, setHourHistogram] = useState(Array(24).fill(0));
  const [weekCounts, setWeekCounts] = useState([]); // [{date, catSightings}]
  const [todayCount, setTodayCount] = useState(0);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      // Passages récents (pour "vu il y a Xh" + histogramme par heure)
      const sightingsQuery = query(
        collection(db, 'catSightings'), orderBy('timestamp', 'desc'), limit(400)
      );
      const sightingsSnap = await getDocs(sightingsQuery);
      const sightings = sightingsSnap.docs.map(d => d.data());
      if (sightings.length > 0) {
        setLastSeen(sightings[0].timestamp?.toDate() || null);
        const histogram = Array(24).fill(0);
        for (const s of sightings) {
          const date = s.timestamp?.toDate();
          if (date) histogram[date.getHours()] += 1;
        }
        setHourHistogram(histogram);
        const today = new Date().toDateString();
        setTodayCount(sightings.filter(s => s.timestamp?.toDate().toDateString() === today).length);
      } else {
        setLastSeen(null);
        setHourHistogram(Array(24).fill(0));
        setTodayCount(0);
      }

      // Passages par jour (7 derniers jours, calculés par le Pi)
      const statsQuery = query(collection(db, 'dailyStats'), orderBy('date', 'desc'), limit(7));
      const statsSnap = await getDocs(statsQuery);
      setWeekCounts(
        statsSnap.docs.map(d => ({ date: d.data().date, count: d.data().catSightings || 0 })).reverse()
      );
    } catch (err) {
      console.warn('Chargement stats chat:', err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const maxHour = Math.max(...hourHistogram, 1);
  const alert = lastSeen && (Date.now() - lastSeen.getTime()) > ALERT_HOURS * 3600000;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={loading} onRefresh={load} tintColor="#e67e22" />
      }
    >
      {alert && (
        <View style={styles.alertBox}>
          <Text style={styles.alertText}>
            ⚠️ Chat pas vu depuis plus de {ALERT_HOURS} h. Vérifie la gamelle !
          </Text>
        </View>
      )}

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Dernière apparition</Text>
        {lastSeen ? (
          <>
            <Text style={styles.lastSeenValue}>Vu {formatDelay(Date.now() - lastSeen.getTime())}</Text>
            <Text style={styles.hint}>
              Passages repérés aujourd'hui : {todayCount}
            </Text>
          </>
        ) : (
          <Text style={styles.hint}>Aucun passage détecté pour l'instant</Text>
        )}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Heures d'activité (derniers passages)</Text>
        <View style={styles.histogram}>
          {hourHistogram.map((count, hour) => (
            <View key={hour} style={styles.histogramColumn}>
              <View style={styles.histogramBarArea}>
                <View
                  style={[
                    styles.histogramBar,
                    { height: `${Math.round((count / maxHour) * 100)}%` },
                    count === 0 && styles.histogramBarEmpty,
                  ]}
                />
              </View>
            </View>
          ))}
        </View>
        <View style={styles.histogramAxis}>
          <Text style={styles.axisLabel}>0h</Text>
          <Text style={styles.axisLabel}>6h</Text>
          <Text style={styles.axisLabel}>12h</Text>
          <Text style={styles.axisLabel}>18h</Text>
          <Text style={styles.axisLabel}>23h</Text>
        </View>
      </View>

      {weekCounts.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Passages par jour</Text>
          <View style={styles.chart}>
            {weekCounts.map(s => (
              <View key={s.date} style={styles.chartColumn}>
                <Text style={styles.chartValue}>{s.count || ''}</Text>
                <View style={styles.chartBarArea}>
                  <View
                    style={[
                      styles.chartBar,
                      { height: `${Math.min(100, Math.round((s.count / Math.max(...weekCounts.map(w => w.count), 1)) * 100))}%` },
                    ]}
                  />
                </View>
                <Text style={styles.chartLabel}>{s.date.slice(8)}</Text>
              </View>
            ))}
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f5f5f5' },
  alertBox: {
    backgroundColor: '#fdecea', borderColor: '#c0392b', borderWidth: 1,
    borderRadius: 10, padding: 12, marginBottom: 12,
  },
  alertText: { color: '#c0392b', fontWeight: '600' },
  card: { backgroundColor: '#fff', borderRadius: 10, padding: 14, marginBottom: 12 },
  cardTitle: { fontSize: 13, fontWeight: '600', color: '#555', marginBottom: 8 },
  lastSeenValue: { fontSize: 20, fontWeight: 'bold', color: '#333' },
  hint: { fontSize: 12, color: '#888', marginTop: 4 },
  histogram: { flexDirection: 'row', height: 90 },
  histogramColumn: { flex: 1, alignItems: 'center' },
  histogramBarArea: { flex: 1, width: '60%', justifyContent: 'flex-end' },
  histogramBar: { backgroundColor: '#e67e22', borderRadius: 2 },
  histogramBarEmpty: { backgroundColor: 'transparent' },
  histogramAxis: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  axisLabel: { fontSize: 10, color: '#888' },
  chart: { flexDirection: 'row', height: 100 },
  chartColumn: { flex: 1, alignItems: 'center', justifyContent: 'flex-end' },
  chartValue: { fontSize: 10, color: '#888' },
  chartBarArea: { flex: 1, width: '60%', justifyContent: 'flex-end' },
  chartBar: { backgroundColor: '#e67e22', borderRadius: 3 },
  chartLabel: { fontSize: 10, color: '#888', marginTop: 4 },
});
