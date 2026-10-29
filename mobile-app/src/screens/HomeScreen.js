import React, { useEffect, useState } from 'react';
import { View, Text, Button, FlatList, StyleSheet } from 'react-native';
import { collection, query, orderBy, limit, onSnapshot } from 'firebase/firestore';
import { db } from '../services/firebase';

export default function HomeScreen({ navigation }) {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    const q = query(collection(db, 'events'), orderBy('timestamp', 'desc'), limit(20));
    const unsub = onSnapshot(q, (snap) => {
      setEvents(snap.docs.map(d => ({ id: d.id, ...d.data() })));
    });
    return () => unsub();
  }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>
        {events[0]?.bowlEmpty ? '🚨 Gamelle VIDE' : '✅ Gamelle pleine'}
      </Text>
      <Button title="📸 Voir les photos" onPress={() => navigation.navigate('Gallery')} />
      <FlatList
        data={events}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <Text>{item.bowlEmpty ? '🚨 Vide' : '🍽️ Mangé'} — {new Date(item.timestamp?.toDate()).toLocaleString('fr-FR')}</Text>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, backgroundColor: '#f5f5f5' },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 16 },
});