// src/pages/Login.js
import React, { useState } from 'react';
import { supabase } from '../lib/supabase';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { FaDumbbell } from 'react-icons/fa';

const Login = () => {
  const navigate = useNavigate();

  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const getReadableError = (message) => {
    if (!message) return 'A aparut o eroare. Incearca din nou.';

    const lower = message.toLowerCase();

    if (lower.includes('invalid login credentials')) {
      return 'Email sau parola incorecta.';
    }

    if (lower.includes('user already registered')) {
      return 'Exista deja un cont cu acest email.';
    }

    if (lower.includes('password should be at least')) {
      return 'Parola este prea scurta.';
    }

    if (lower.includes('invalid email')) {
      return 'Email invalid.';
    }

    return message;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        const usernameFromEmail = email.split('@')[0];

        const { error: signUpError } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: {
              full_name: fullName,
              username: usernameFromEmail,
            },
          },
        });

        if (signUpError) {
          throw signUpError;
        }

        alert('Cont creat cu succes. Acum te poti loga.');
        setIsRegister(false);
        setPassword('');
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });

        if (signInError) {
          throw signInError;
        }

        navigate('/home');
      }
    } catch (err) {
      console.error(err);
      setError(getReadableError(err?.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'radial-gradient(circle at center, #1a1a2e 0%, #000 100%)',
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: -50 }}
        animate={{ opacity: 1, y: 0 }}
        className="cyber-card"
        style={{
          padding: '50px 40px',
          width: '380px',
          textAlign: 'center',
          border: '1px solid var(--neon-cyan)',
          boxShadow: '0 0 20px rgba(0, 229, 255, 0.2)',
        }}
      >
        <div style={{ marginBottom: '30px' }}>
          <motion.div
            animate={{ rotate: [0, 10, -10, 0] }}
            transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
            style={{
              display: 'inline-block',
              padding: '15px',
              borderRadius: '50%',
              background: 'rgba(0, 229, 255, 0.1)',
              marginBottom: '15px',
            }}
          >
            <FaDumbbell
              size={50}
              color="var(--neon-cyan)"
              style={{ filter: 'drop-shadow(0 0 8px var(--neon-cyan))' }}
            />
          </motion.div>

          <h1
            style={{
              color: '#fff',
              margin: 0,
              fontFamily: 'Orbitron',
              fontSize: '2.5rem',
              letterSpacing: '4px',
            }}
          >
            FITAPP
          </h1>
          <p
            style={{
              color: 'var(--neon-purple)',
              margin: '5px 0 0 0',
              fontSize: '0.8rem',
              letterSpacing: '2px',
              textTransform: 'uppercase',
            }}
          >
            AI Performance Analytics
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}
        >
          {isRegister && (
            <input
              className="cyber-input"
              type="text"
              placeholder="Nume complet"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required={isRegister}
            />
          )}

          <input
            className="cyber-input"
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <input
            className="cyber-input"
            type="password"
            placeholder="Parola"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          {error && (
            <div
              style={{
                color: '#ff4d4d',
                fontSize: '13px',
                background: 'rgba(255,0,0,0.1)',
                padding: '10px',
                borderRadius: '4px',
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            className="cyber-btn"
            style={{ marginTop: '10px', fontSize: '1.1rem' }}
            disabled={loading}
          >
            {loading
              ? isRegister
                ? 'SE CREEAZA CONTUL...'
                : 'SE AUTENTIFICA...'
              : isRegister
              ? 'INREGISTRARE'
              : 'AUTENTIFICARE'}
          </button>
        </form>

        <p
          style={{
            marginTop: '25px',
            cursor: 'pointer',
            fontSize: '17px',
            color: '#888',
            transition: '0.3s',
          }}
          onClick={() => {
            if (loading) return;
            setIsRegister(!isRegister);
            setError('');
          }}
          onMouseEnter={(e) => {
            e.target.style.color = 'var(--neon-cyan)';
          }}
          onMouseLeave={(e) => {
            e.target.style.color = '#888';
          }}
        >
          {isRegister ? 'Ai deja cont? Logheaza-te' : 'Nu ai cont? Creeaza unul'}
        </p>
      </motion.div>
    </div>
  );
};

export default Login;