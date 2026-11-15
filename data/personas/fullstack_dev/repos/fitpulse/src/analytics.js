import firebase from '@react-native-firebase/app';
import analytics from '@react-native-firebase/analytics';

// Ensure Firebase app is initialized (same config as in App.js)
if (!firebase.apps.length) {
  firebase.initializeApp({
    apiKey: "AIzaSyD-ExampleKey",
    authDomain: "fitnessstudio-12345.firebaseapp.com",
    projectId: "fitnessstudio-12345",
    storageBucket: "fitnessstudio-12345.appspot.com",
    messagingSenderId: "1234567890",
    appId: "1:1234567890:web:abcdef123456"
  });
}

export const logClassView = async (classId, className) => {
  try {
    await analytics().logEvent('view_class', {
      class_id: classId,
      class_name: className,
      timestamp: Date.now()
    });
  } catch (e) {
    console.warn('Analytics log failed:', e);
  }
};
