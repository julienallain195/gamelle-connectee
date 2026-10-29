import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, SectionList, Image, Dimensions, StyleSheet, TouchableOpacity, ActivityIndicator, Alert, RefreshControl } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { VideoView, useVideoPlayer } from 'expo-video';
import { collection, query, orderBy, limit, getDocs, onSnapshot, addDoc, serverTimestamp } from 'firebase/firestore';
import { ref, getDownloadURL } from 'firebase/storage';
import { db, storage } from '../services/firebase';

const { width } = Dimensions.get('window');
const DEVICE_ID = 'raspberry-pi-1';

function Chip({ label, active, onPress }) {
  return (
    <TouchableOpacity style={[styles.chip, active && styles.chipActive]} onPress={onPress}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

// Une cellule de la grille : photo, ou vidéo (lue au tap)
function PhotoCell({ item }) {
  const [playing, setPlaying] = useState(false);
  const player = useVideoPlayer(item.videoUrl || '', p => {
    p.loop = true;
    p.muted = true;
  });

  if (playing && item.videoUrl) {
    return (
      <View style={[styles.cell, styles.videoCell]}>
        <VideoView
          player={player}
          style={styles.video}
          contentFit="cover"
          allowsFullscreen={false}
        />
        <TouchableOpacity style={styles.closeVideo} onPress={() => setPlaying(false)}>
          <Ionicons name="close" size={16} color="#fff" />
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <TouchableOpacity style={styles.cell} activeOpacity={0.9} onPress={() => item.videoUrl && setPlaying(true)}>
      {item.url ? (
        <Image source={{ uri: item.url }} style={styles.image} />
      ) : (
        <View style={[styles.image, styles.imageEmpty]} />
      )}
      {item.catSeen && (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>🐱</Text>
        </View>
      )}
      {item.videoUrl && (
        <View style={styles.playBadge}>
          <Ionicons name="play" size={14} color="#fff" />
        </View>
      )}
      {item.occluded && (
        <View style={styles.occludedBadge}>
          <Text style={styles.badgeText}>🚧</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

export default function PhotosScreen() {
  const [sections, setSections] = useState([]);
  const [onlyCat, setOnlyCat] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const pendingUnsub = useRef(null);

  const load = useCallback(async () => {
    const q = query(collection(db, 'events'), orderBy('timestamp', 'desc'), limit(60));
    const snap = await getDocs(q);
    const items = await Promise.all(
      snap.docs.filter(d => d.data().photoPath || d.data().videoPath).map(async d => {
        const data = d.data();
        const item = {
          id: d.id,
          catSeen: data.catSeen === true,
          occluded: data.occluded === true,
          timestamp: data.timestamp,
          videoUrl: null,
          url: null,
        };
        if (data.photoPath) {
          item.url = await getDownloadURL(ref(storage, data.photoPath)).catch(() => null);
        }
        if (data.videoPath) {
          item.videoUrl = await getDownloadURL(ref(storage, data.videoPath)).catch(() => null);
        }
        return item;
      })
    );

    // Groupement par journée (sections) + compteur de passages par jour
    const byDay = new Map();
    for (const item of items) {
      const label = item.timestamp?.toDate().toLocaleDateString('fr-FR', {
        weekday: 'long', day: 'numeric', month: 'long',
      }) || 'Date inconnue';
      if (!byDay.has(label)) byDay.set(label, []);
      byDay.get(label).push(item);
    }
    setSections(
      [...byDay.entries()].map(([label, dayItems]) => ({
        key: label,
        title: label.charAt(0).toUpperCase() + label.slice(1),
        catCount: dayItems.filter(i => i.catSeen).length,
        data: dayItems,
      }))
    );
  }, []);

  useEffect(() => {
    load().catch(err => console.warn('Chargement photos:', err.message));
    return () => { if (pendingUnsub.current) pendingUnsub.current(); };
  }, [load]);

  // Demande au Raspberry de prendre une photo maintenant.
  async function requestCapture() {
    if (requesting) return;
    setRequesting(true);
    try {
      const docRef = await addDoc(collection(db, 'commands'), {
        type: 'capture',
        deviceId: DEVICE_ID,
        status: 'pending',
        requestedAt: serverTimestamp(),
      });
      const unsub = onSnapshot(docRef, (snap) => {
        const data = snap.data();
        if (data && data.status !== 'pending') {
          unsub();
          pendingUnsub.current = null;
          setRequesting(false);
          if (data.status === 'done') {
            if (data.skippedQuiet) {
              Alert.alert('Heures silencieuses', 'Le Raspberry n\'a pas capturé : plage horaire de repos.');
            }
            load().catch(() => {});
          } else {
            Alert.alert('Capture impossible', 'Le Raspberry n\'a pas pu traiter la demande.');
          }
        }
      });
      pendingUnsub.current = unsub;
    } catch (err) {
      setRequesting(false);
      console.warn('Demande de capture impossible:', err.message);
    }
  }

  async function refresh() {
    setRefreshing(true);
    await load().catch(() => {});
    setRefreshing(false);
  }

  const visibleSections = onlyCat
    ? sections.map(s => ({ ...s, data: s.data.filter(i => i.catSeen) })).filter(s => s.data.length > 0)
    : sections;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.chips}>
          <Chip label="Toutes" active={!onlyCat} onPress={() => setOnlyCat(false)} />
          <Chip label="Avec le chat" active={onlyCat} onPress={() => setOnlyCat(true)} />
        </View>
        <TouchableOpacity
          style={styles.captureButton}
          onPress={requestCapture}
          disabled={requesting}
          accessibilityLabel="Voir la gamelle maintenant"
        >
          {requesting
            ? <ActivityIndicator color="#fff" size="small" />
            : <Ionicons name="camera" size={22} color="#fff" />}
        </TouchableOpacity>
      </View>

      <SectionList
        sections={visibleSections}
        keyExtractor={item => item.id}
        numColumns={2}
        stickySectionHeadersEnable={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor="#e67e22" />
        }
        renderSectionHeader={({ section }) => (
          <View style={styles.dayHeader}>
            <Text style={styles.dayTitle}>{section.title}</Text>
            <Text style={styles.dayCount}>
              {section.catCount > 0 ? `🐱 ${section.catCount} passage${section.catCount > 1 ? 's' : ''}` : '—'}
            </Text>
          </View>
        )}
        renderItem={({ item }) => <PhotoCell item={item} />}
        ListEmptyComponent={
          <Text style={styles.emptyList}>
            {onlyCat
              ? 'Pas encore de photo avec le chat repéré.'
              : 'Aucune photo. Appuie sur l\'appareil photo en haut à droite pour demander une capture.'}
          </Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 8, backgroundColor: '#f5f5f5' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 8, paddingVertical: 6,
  },
  chips: { flexDirection: 'row' },
  chip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: '#e0e0e0', marginRight: 8 },
  chipActive: { backgroundColor: '#e67e22' },
  chipText: { fontSize: 13, color: '#555' },
  chipTextActive: { color: '#fff', fontWeight: '600' },
  captureButton: {
    backgroundColor: '#e67e22', width: 44, height: 44, borderRadius: 22,
    alignItems: 'center', justifyContent: 'center',
  },
  dayHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 8, paddingTop: 12, paddingBottom: 6,
  },
  dayTitle: { fontWeight: '600', fontSize: 14, color: '#444' },
  dayCount: { fontSize: 12, color: '#888' },
  cell: { width: width / 2 - 16, height: width / 2 - 16, margin: 4 },
  image: { width: '100%', height: '100%', borderRadius: 8 },
  imageEmpty: { backgroundColor: '#ddd', borderRadius: 8 },
  videoCell: { borderRadius: 8, overflow: 'hidden' },
  video: { width: '100%', height: '100%' },
  badge: {
    position: 'absolute', bottom: 6, right: 6,
    backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 10,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  badgeText: { fontSize: 14 },
  playBadge: {
    position: 'absolute', top: 6, right: 6,
    backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 12,
    padding: 4,
  },
  occludedBadge: {
    position: 'absolute', top: 6, left: 6,
    backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 10,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  closeVideo: {
    position: 'absolute', top: 6, right: 6,
    backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 12, padding: 4,
  },
  emptyList: { textAlign: 'center', color: '#888', marginTop: 32, paddingHorizontal: 16 },
});
