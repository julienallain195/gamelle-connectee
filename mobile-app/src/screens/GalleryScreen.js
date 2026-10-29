import React, { useEffect, useState } from 'react';
import { View, FlatList, Image, Dimensions, StyleSheet } from 'react-native';
import { collection, query, orderBy, limit, getDocs } from 'firebase/firestore';
import { ref, getDownloadURL } from 'firebase/storage';
import { db, storage } from '../services/firebase';

const { width } = Dimensions.get('window');

export default function GalleryScreen() {
  const [photos, setPhotos] = useState([]);

  useEffect(() => {
    async function load() {
      const q = query(collection(db, 'events'), orderBy('timestamp', 'desc'), limit(30));
      const snap = await getDocs(q);
      const items = await Promise.all(
        snap.docs.filter(d => d.data().photoPath).map(async d => ({
          id: d.id,
          url: await getDownloadURL(ref(storage, d.data().photoPath)),
        }))
      );
      setPhotos(items);
    }
    load();
  }, []);

  return (
    <FlatList
      data={photos}
      keyExtractor={item => item.id}
      numColumns={2}
      renderItem={({ item }) => (
        <Image source={{ uri: item.url }} style={styles.image} />
      )}
    />
  );
}

const styles = StyleSheet.create({
  image: { width: width / 2 - 8, height: width / 2 - 8, margin: 4, borderRadius: 8 },
});