// src/context/AuthContext.js
import React, { createContext, useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [session, setSession] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    const loadSession = async () => {
      try {
        const {
          data: { session },
          error,
        } = await supabase.auth.getSession();

        if (error) {
          console.error('Eroare la getSession:', error);
        }

        if (!isMounted) return;

        setSession(session || null);
        setUser(session?.user || null);
      } catch (err) {
        console.error('Eroare neasteptata la initializarea sesiunii:', err);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session || null);
      setUser(session?.user || null);
      setLoading(false);
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const logout = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) {
      console.error('Eroare la logout:', error);
      return;
    }

    setSession(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        loading,
        isAuthenticated: !!user,
        logout,
      }}
    >
      {!loading && children}
    </AuthContext.Provider>
  );
};