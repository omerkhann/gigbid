import React, {useEffect, useState} from 'react';
import {SafeAreaView, FlatList, Text, StyleSheet} from 'react-native';
import firebase from '@react-native-firebase/app';
import firestore from '@react-native-firebase/firestore';

// Firebase configuration (public keys only)
const firebaseConfig = {
  apiKey: "AIzaSyD-ExampleKey",
  authDomain: "fitnessstudio-12345.firebaseapp.com",
  projectId: "fitnessstudio-12345",
  storageBucket: "fitnessstudio-12345.appspot.com",
  messagingSenderId: "1234567890",
  appId: "1:1234567890:web:abcdef123456"
};

if (!firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}

export default function App() {
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = firestore()
      .collection('classes')
      .orderBy('startTime', 'asc')
      .onSnapshot(snapshot => {
        const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
        setClasses(data);
        setLoading(false);
      }, error => {
        console.error('Error fetching classes: ', error);
        setLoading(false);
      });
    return () => unsubscribe();
  }, []);

  const renderItem = ({item}) => (
    <View style={styles.card}>
      <Text style={styles.title}>{item.name}</Text>
      <Text>{new Date(item.startTime.seconds * 1000).toLocaleTimeString()}</Text>
      <Text>Instructor: {item.instructor}</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      {loading ? <Text style={styles.loading}>Loading classes...</Text> :
        <FlatList
          data={classes}
          keyExtractor={item => item.id}
          renderItem={renderItem}
          contentContainerStyle={styles.list}
        />}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f5f5' },
  list: { padding: 16 },
  card: { backgroundColor: '#fff', padding: 16, marginBottom: 12, borderRadius: 8, elevation: 2 },
  title: { fontSize: 18, fontWeight: 'bold', marginBottom: 4 },
  loading: { textAlign: 'center', marginTop: 20 }
});
