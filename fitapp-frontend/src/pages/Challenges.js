// src/pages/Challenges.js
import React, { useContext, useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { supabase } from '../lib/supabase';
import { AuthContext } from '../context/AuthContext';
import { FaTrophy, FaClock, FaUsers, FaChevronDown, FaChevronUp, FaPlus, FaTimes, FaTrash } from 'react-icons/fa';

const EXERCISE_COLORS = {
  Genoflexiune: '#00f3ff',
  Flotare: '#bc13fe',
  Deadlift: '#ff6b35',
  Fandare: '#00ff99',
  Abdomene: '#ffcc00',
  Tractiuni: '#ff4d6d',
};

const EXERCISE_ICONS = {
  Genoflexiune: '🦵',
  Flotare: '💪',
  Deadlift: '🏋️',
  Fandare: '🚶',
  Abdomene: '🔥',
  Tractiuni: '🤸',
};

const METRIC_LABELS = {
  max_reps: 'Maxim Repetări',
  best_score: 'Cel Mai Bun Scor',
  total_reps: 'Total Repetări',
  consistency: 'Consistență',
};

const METRIC_UNITS = {
  max_reps: ' rep',
  best_score: '%',
  total_reps: ' rep',
  consistency: '%',
};

function timeRemaining(endAt) {
  const diff = new Date(endAt) - new Date();
  if (diff <= 0) return 'Terminat';
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  if (days > 0) return `${days}z ${hours}h rămas`;
  if (hours > 0) return `${hours}h ${minutes}m rămas`;
  return `${minutes}m rămas`;
}

function isEnded(challenge) {
  return new Date(challenge.end_at) < new Date() || !challenge.is_active;
}

const RANK_COLORS = ['#ffd700', '#c0c0c0', '#cd7f32'];

const inputStyle = {
  width: '100%',
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid #2a2a35',
  borderRadius: '8px',
  color: '#fff',
  padding: '10px 14px',
  fontSize: '13px',
  outline: 'none',
  boxSizing: 'border-box',
  fontFamily: 'inherit',
};

const labelStyle = {
  display: 'block',
  fontSize: '11px',
  color: '#555',
  marginBottom: '6px',
  fontFamily: 'Orbitron',
  letterSpacing: '1px',
};

const Challenges = () => {
  const { user } = useContext(AuthContext);
  const [challenges, setChallenges] = useState([]);
  const [myEntries, setMyEntries] = useState({});
  const [leaderboards, setLeaderboards] = useState({});
  const [expandedId, setExpandedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [joining, setJoining] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [filter, setFilter] = useState('active');
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [form, setForm] = useState({
    title: '',
    description: '',
    exercise_type: 'Flotare',
    metric_type: 'max_reps',
    start_at: '',
    end_at: '',
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const { data: cData, error: cError } = await supabase
        .from('challenges')
        .select('*, created_by')
        .eq('is_public', true)
        .order('start_at', { ascending: false });

      if (cError) throw cError;
      setChallenges(cData || []);

      if (user) {
        const { data: eData } = await supabase
          .from('challenge_entries')
          .select('*')
          .eq('user_id', user.id);

        const map = {};
        (eData || []).forEach((e) => { map[e.challenge_id] = e; });
        setMyEntries(map);
      }
    } catch (err) {
      console.error('Eroare la încărcare provocări:', err);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const loadLeaderboard = useCallback(async (challengeId) => {
    if (leaderboards[challengeId]) return;
    const { data, error } = await supabase
      .from('challenge_entries')
      .select('value, user_id, updated_at, profiles ( full_name, username )')
      .eq('challenge_id', challengeId)
      .order('value', { ascending: false })
      .limit(10);

    if (!error) {
      setLeaderboards((prev) => ({ ...prev, [challengeId]: data || [] }));
    }
  }, [leaderboards]);

  const handleToggleExpand = (id) => {
    if (expandedId === id) {
      setExpandedId(null);
    } else {
      setExpandedId(id);
      loadLeaderboard(id);
    }
  };

  const handleJoin = async (challengeId) => {
    if (!user) return;
    setJoining(challengeId);
    try {
      const { error } = await supabase
        .from('challenge_entries')
        .insert({ challenge_id: challengeId, user_id: user.id, value: 0 });

      if (!error) {
        setMyEntries((prev) => ({
          ...prev,
          [challengeId]: { challenge_id: challengeId, user_id: user.id, value: 0 },
        }));
        setLeaderboards((prev) => { const u = { ...prev }; delete u[challengeId]; return u; });
        if (expandedId === challengeId) loadLeaderboard(challengeId);
      }
    } finally {
      setJoining(null);
    }
  };

  const handleLeave = async (challengeId) => {
    if (!user) return;
    setJoining(challengeId);
    try {
      const { error } = await supabase
        .from('challenge_entries')
        .delete()
        .eq('challenge_id', challengeId)
        .eq('user_id', user.id);

      if (!error) {
        setMyEntries((prev) => { const u = { ...prev }; delete u[challengeId]; return u; });
        setLeaderboards((prev) => { const u = { ...prev }; delete u[challengeId]; return u; });
        if (expandedId === challengeId) loadLeaderboard(challengeId);
      }
    } finally {
      setJoining(null);
    }
  };

  const handleDelete = async (challengeId) => {
    setDeleting(challengeId);
    try {
      const { error } = await supabase
        .from('challenges')
        .delete()
        .eq('id', challengeId);

      if (!error) {
        setChallenges((prev) => prev.filter((c) => c.id !== challengeId));
        setMyEntries((prev) => { const u = { ...prev }; delete u[challengeId]; return u; });
        setLeaderboards((prev) => { const u = { ...prev }; delete u[challengeId]; return u; });
        if (expandedId === challengeId) setExpandedId(null);
      }
    } finally {
      setDeleting(null);
      setConfirmDelete(null);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreateError('');
    if (!form.title.trim()) { setCreateError('Titlul este obligatoriu.'); return; }
    if (!form.start_at || !form.end_at) { setCreateError('Datele sunt obligatorii.'); return; }
    if (new Date(form.end_at) <= new Date(form.start_at)) {
      setCreateError('Data de sfârșit trebuie să fie după data de start.');
      return;
    }
    setCreating(true);
    try {
      const { data, error } = await supabase
        .from('challenges')
        .insert({
          title: form.title.trim(),
          description: form.description.trim() || null,
          exercise_type: form.exercise_type,
          metric_type: form.metric_type,
          start_at: new Date(form.start_at).toISOString(),
          end_at: new Date(form.end_at).toISOString(),
          is_public: true,
          is_active: true,
          created_by: user.id,
        })
        .select()
        .single();

      if (error) throw error;
      setChallenges((prev) => [data, ...prev]);
      setShowCreate(false);
      setForm({ title: '', description: '', exercise_type: 'Flotare', metric_type: 'max_reps', start_at: '', end_at: '' });
      setFilter('active');
    } catch (err) {
      setCreateError(err.message || 'Eroare la creare.');
    } finally {
      setCreating(false);
    }
  };

  const filtered = challenges.filter((c) =>
    filter === 'active' ? !isEnded(c) : isEnded(c)
  );

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
          style={{
            width: 40, height: 40,
            border: '3px solid #222',
            borderTopColor: 'var(--neon-cyan)',
            borderRadius: '50%',
          }}
        />
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '32px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <FaTrophy size={28} color="var(--neon-cyan)" style={{ filter: 'drop-shadow(0 0 8px var(--neon-cyan))' }} />
            <h1 style={{ fontFamily: 'Orbitron', fontSize: '24px', margin: 0, letterSpacing: '2px' }}>
              PROVOCARI
            </h1>
          </div>
          <p style={{ color: '#555', margin: 0, fontSize: '14px' }}>
            Participă la provocări și urcă în clasament
          </p>
        </div>
        <button
          onClick={() => { setShowCreate(true); setCreateError(''); }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 20px',
            background: 'linear-gradient(135deg, rgba(0,243,255,0.15), rgba(0,243,255,0.05))',
            border: '1px solid var(--neon-cyan)',
            borderRadius: '10px',
            color: 'var(--neon-cyan)',
            cursor: 'pointer',
            fontSize: '12px',
            fontFamily: 'Orbitron',
            letterSpacing: '1px',
            boxShadow: '0 0 14px rgba(0,243,255,0.15)',
            transition: 'all 0.2s',
          }}
        >
          <FaPlus size={11} />
          Provocare Nouă
        </button>
      </div>

      {/* Create modal */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.75)',
              zIndex: 999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '20px',
            }}
            onClick={(e) => { if (e.target === e.currentTarget) setShowCreate(false); }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              style={{
                background: '#0a0a0f',
                border: '1px solid #2a2a35',
                borderRadius: '16px',
                padding: '32px',
                width: '100%',
                maxWidth: '520px',
                position: 'relative',
              }}
            >
              <div style={{ height: '3px', background: 'linear-gradient(90deg, var(--neon-cyan), #bc13fe)', borderRadius: '2px', marginBottom: '24px' }} />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2 style={{ fontFamily: 'Orbitron', fontSize: '16px', margin: 0, letterSpacing: '2px' }}>
                  PROVOCARE NOUĂ
                </h2>
                <button
                  onClick={() => setShowCreate(false)}
                  style={{ background: 'transparent', border: 'none', color: '#555', cursor: 'pointer', padding: '4px' }}
                >
                  <FaTimes size={16} />
                </button>
              </div>

              <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={labelStyle}>Titlu *</label>
                  <input
                    type="text"
                    value={form.title}
                    onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                    placeholder="ex: 100 Flotări în 7 zile"
                    maxLength={80}
                    style={inputStyle}
                  />
                </div>

                <div>
                  <label style={labelStyle}>Descriere</label>
                  <textarea
                    value={form.description}
                    onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                    placeholder="Descrie provocarea (opțional)"
                    rows={3}
                    maxLength={300}
                    style={{ ...inputStyle, resize: 'vertical', minHeight: '80px' }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={labelStyle}>Exercițiu *</label>
                    <select
                      value={form.exercise_type}
                      onChange={(e) => setForm((f) => ({ ...f, exercise_type: e.target.value }))}
                      style={inputStyle}
                    >
                      {['Genoflexiune', 'Flotare', 'Deadlift', 'Fandare', 'Abdomene', 'Tractiuni'].map((ex) => (
                        <option key={ex} value={ex}>{ex}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={labelStyle}>Metrică *</label>
                    <select
                      value={form.metric_type}
                      onChange={(e) => setForm((f) => ({ ...f, metric_type: e.target.value }))}
                      style={inputStyle}
                    >
                      <option value="max_reps">Maxim Repetări</option>
                      <option value="best_score">Cel Mai Bun Scor</option>
                      <option value="total_reps">Total Repetări</option>
                      <option value="consistency">Consistență</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label style={labelStyle}>Data start *</label>
                    <input
                      type="datetime-local"
                      value={form.start_at}
                      onChange={(e) => setForm((f) => ({ ...f, start_at: e.target.value }))}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Data sfârșit *</label>
                    <input
                      type="datetime-local"
                      value={form.end_at}
                      onChange={(e) => setForm((f) => ({ ...f, end_at: e.target.value }))}
                      style={inputStyle}
                    />
                  </div>
                </div>

                {createError && (
                  <div style={{ color: '#ff4d4d', fontSize: '13px', background: 'rgba(255,77,77,0.08)', border: '1px solid rgba(255,77,77,0.2)', borderRadius: '8px', padding: '10px 14px' }}>
                    {createError}
                  </div>
                )}

                <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
                  <button
                    type="button"
                    onClick={() => setShowCreate(false)}
                    style={{
                      padding: '10px 20px',
                      background: 'transparent',
                      border: '1px solid #333',
                      borderRadius: '8px',
                      color: '#666',
                      cursor: 'pointer',
                      fontSize: '13px',
                    }}
                  >
                    Anulează
                  </button>
                  <button
                    type="submit"
                    disabled={creating}
                    style={{
                      padding: '10px 24px',
                      background: 'linear-gradient(135deg, rgba(0,243,255,0.2), rgba(0,243,255,0.08))',
                      border: '1px solid var(--neon-cyan)',
                      borderRadius: '8px',
                      color: 'var(--neon-cyan)',
                      cursor: creating ? 'not-allowed' : 'pointer',
                      fontSize: '13px',
                      fontFamily: 'Orbitron',
                      fontWeight: 'bold',
                      letterSpacing: '1px',
                      opacity: creating ? 0.6 : 1,
                    }}
                  >
                    {creating ? 'Se creează...' : 'Creează'}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '28px' }}>
        {[{ key: 'active', label: 'Active' }, { key: 'ended', label: 'Terminate' }].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            style={{
              padding: '8px 22px',
              background: filter === tab.key ? 'rgba(0, 243, 255, 0.1)' : 'transparent',
              border: `1px solid ${filter === tab.key ? 'var(--neon-cyan)' : '#333'}`,
              borderRadius: '8px',
              color: filter === tab.key ? 'var(--neon-cyan)' : '#555',
              cursor: 'pointer',
              fontSize: '12px',
              fontFamily: 'Orbitron',
              letterSpacing: '1px',
              transition: 'all 0.2s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div style={{ textAlign: 'center', color: '#333', paddingTop: '80px', fontSize: '15px' }}>
          Nicio provocare {filter === 'active' ? 'activă' : 'terminată'} momentan.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {filtered.map((c, i) => {
            const joined = !!myEntries[c.id];
            const myEntry = myEntries[c.id];
            const ended = isEnded(c);
            const color = EXERCISE_COLORS[c.exercise_type] || 'var(--neon-cyan)';
            const expanded = expandedId === c.id;
            const lb = leaderboards[c.id] || [];
            const myRank = joined ? lb.findIndex((e) => e.user_id === user?.id) + 1 : 0;
            const isOwner = c.created_by === user?.id;

            return (
              <motion.div
                key={c.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                style={{
                  background: 'rgba(10, 10, 15, 0.95)',
                  border: `1px solid ${joined ? color + '60' : '#1e1e28'}`,
                  borderRadius: '12px',
                  overflow: 'hidden',
                  boxShadow: joined ? `0 0 24px ${color}15` : 'none',
                  transition: 'border-color 0.3s, box-shadow 0.3s',
                }}
              >
                <div style={{ height: '3px', background: `linear-gradient(90deg, ${color}, transparent)` }} />

                <div style={{ padding: '20px 24px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '22px' }}>{EXERCISE_ICONS[c.exercise_type]}</span>
                        <h3 style={{ margin: 0, fontSize: '15px', fontFamily: 'Orbitron', color: '#fff', letterSpacing: '1px' }}>
                          {c.title}
                        </h3>
                        {joined && (
                          <span style={{
                            background: `${color}20`,
                            border: `1px solid ${color}80`,
                            color: color,
                            fontSize: '9px',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontFamily: 'Orbitron',
                            letterSpacing: '1px',
                          }}>
                            ÎNSCRIS
                          </span>
                        )}
                      </div>

                      {c.description && (
                        <p style={{ margin: '0 0 14px', color: '#666', fontSize: '13px', lineHeight: '1.6' }}>
                          {c.description}
                        </p>
                      )}

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        <span style={{
                          background: `${color}15`,
                          border: `1px solid ${color}40`,
                          color: color,
                          fontSize: '11px',
                          padding: '3px 10px',
                          borderRadius: '6px',
                        }}>
                          {c.exercise_type}
                        </span>
                        <span style={{
                          background: 'rgba(188, 19, 254, 0.1)',
                          border: '1px solid rgba(188, 19, 254, 0.3)',
                          color: '#bc13fe',
                          fontSize: '11px',
                          padding: '3px 10px',
                          borderRadius: '6px',
                        }}>
                          {METRIC_LABELS[c.metric_type]}
                        </span>
                        {!ended ? (
                          <span style={{
                            background: 'rgba(255, 204, 0, 0.08)',
                            border: '1px solid rgba(255, 204, 0, 0.3)',
                            color: '#ffcc00',
                            fontSize: '11px',
                            padding: '3px 10px',
                            borderRadius: '6px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '5px',
                          }}>
                            <FaClock size={9} />
                            {timeRemaining(c.end_at)}
                          </span>
                        ) : (
                          <span style={{
                            background: 'rgba(80,80,80,0.1)',
                            border: '1px solid #333',
                            color: '#444',
                            fontSize: '11px',
                            padding: '3px 10px',
                            borderRadius: '6px',
                          }}>
                            Terminat
                          </span>
                        )}
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '12px' }}>
                      {joined && myEntry && (
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: '26px', fontWeight: 'bold', color: color, fontFamily: 'Orbitron', lineHeight: 1 }}>
                            {myEntry.value}{METRIC_UNITS[c.metric_type]}
                          </div>
                          <div style={{ fontSize: '10px', color: '#555', marginTop: '4px', letterSpacing: '1px' }}>
                            VALOAREA TA
                          </div>
                          {myRank > 0 && (
                            <div style={{ fontSize: '11px', color: '#888', marginTop: '4px' }}>
                              #{myRank} în clasament
                            </div>
                          )}
                        </div>
                      )}

                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        {!ended && (
                          joined ? (
                            <button
                              onClick={() => handleLeave(c.id)}
                              disabled={joining === c.id}
                              style={{
                                padding: '8px 16px',
                                background: 'transparent',
                                border: '1px solid #333',
                                borderRadius: '8px',
                                color: '#555',
                                cursor: 'pointer',
                                fontSize: '12px',
                                transition: 'all 0.2s',
                              }}
                            >
                              {joining === c.id ? '...' : 'Retrage-te'}
                            </button>
                          ) : (
                            <button
                              onClick={() => handleJoin(c.id)}
                              disabled={joining === c.id}
                              style={{
                                padding: '8px 20px',
                                background: `linear-gradient(135deg, ${color}20, ${color}08)`,
                                border: `1px solid ${color}`,
                                borderRadius: '8px',
                                color: color,
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: 'bold',
                                fontFamily: 'Orbitron',
                                letterSpacing: '1px',
                                transition: 'all 0.2s',
                                boxShadow: `0 0 12px ${color}20`,
                              }}
                            >
                              {joining === c.id ? '...' : 'Participă'}
                            </button>
                          )
                        )}

                        <button
                          onClick={() => handleToggleExpand(c.id)}
                          style={{
                            padding: '8px 14px',
                            background: expanded ? 'rgba(0,243,255,0.05)' : 'transparent',
                            border: `1px solid ${expanded ? '#333' : '#222'}`,
                            borderRadius: '8px',
                            color: '#666',
                            cursor: 'pointer',
                            fontSize: '12px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            transition: 'all 0.2s',
                          }}
                        >
                          <FaUsers size={12} />
                          {expanded ? <FaChevronUp size={10} /> : <FaChevronDown size={10} />}
                        </button>

                        {isOwner && (
                          <button
                            onClick={() => setConfirmDelete(c.id)}
                            disabled={deleting === c.id}
                            title="Șterge provocarea"
                            style={{
                              padding: '8px 12px',
                              background: 'transparent',
                              border: '1px solid rgba(255,77,77,0.3)',
                              borderRadius: '8px',
                              color: '#ff4d4d',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              transition: 'all 0.2s',
                              opacity: deleting === c.id ? 0.5 : 1,
                            }}
                          >
                            <FaTrash size={12} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  <AnimatePresence>
                    {expanded && (
                      <motion.div
                        key="leaderboard"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        style={{ overflow: 'hidden' }}
                      >
                        <div style={{ borderTop: '1px solid #1a1a22', marginTop: '20px', paddingTop: '20px' }}>
                          <div style={{
                            fontSize: '11px',
                            color: '#444',
                            marginBottom: '14px',
                            fontFamily: 'Orbitron',
                            letterSpacing: '2px',
                          }}>
                            CLASAMENT
                          </div>
                          {lb.length === 0 ? (
                            <div style={{ color: '#333', fontSize: '13px', paddingBottom: '8px' }}>
                              Niciun participant încă.
                            </div>
                          ) : (
                            lb.map((entry, idx) => {
                              const isMe = entry.user_id === user?.id;
                              const rankColor = RANK_COLORS[idx] || '#3a3a40';
                              return (
                                <div
                                  key={entry.user_id}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '14px',
                                    padding: '10px 12px',
                                    background: isMe ? `${color}10` : idx % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent',
                                    borderRadius: '8px',
                                    marginBottom: '3px',
                                    border: isMe ? `1px solid ${color}25` : '1px solid transparent',
                                  }}
                                >
                                  <span style={{
                                    width: '26px',
                                    textAlign: 'center',
                                    fontWeight: 'bold',
                                    color: rankColor,
                                    fontSize: '13px',
                                    fontFamily: 'Orbitron',
                                  }}>
                                    {idx + 1}
                                  </span>
                                  <span style={{
                                    flex: 1,
                                    color: isMe ? '#fff' : '#888',
                                    fontSize: '13px',
                                    fontWeight: isMe ? 'bold' : 'normal',
                                  }}>
                                    {entry.profiles?.full_name || entry.profiles?.username || 'Utilizator'}
                                    {isMe && (
                                      <span style={{ color: color, marginLeft: '8px', fontSize: '10px', fontFamily: 'Orbitron' }}>
                                        (TU)
                                      </span>
                                    )}
                                  </span>
                                  <span style={{
                                    color: isMe ? color : '#666',
                                    fontWeight: 'bold',
                                    fontSize: '14px',
                                    fontFamily: 'Orbitron',
                                  }}>
                                    {entry.value}{METRIC_UNITS[c.metric_type]}
                                  </span>
                                </div>
                              );
                            })
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Confirm delete modal */}
      <AnimatePresence>
        {confirmDelete && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.75)',
              zIndex: 999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '20px',
            }}
            onClick={(e) => { if (e.target === e.currentTarget) setConfirmDelete(null); }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              style={{
                background: '#0a0a0f',
                border: '1px solid rgba(255,77,77,0.3)',
                borderRadius: '14px',
                padding: '28px 32px',
                maxWidth: '400px',
                width: '100%',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '36px', marginBottom: '16px' }}>🗑️</div>
              <h3 style={{ fontFamily: 'Orbitron', fontSize: '15px', margin: '0 0 10px', letterSpacing: '1px' }}>
                Șterge provocarea?
              </h3>
              <p style={{ color: '#666', fontSize: '13px', margin: '0 0 24px', lineHeight: '1.6' }}>
                Această acțiune este ireversibilă. Toți participanții și scorurile lor vor fi șterse.
              </p>
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
                <button
                  onClick={() => setConfirmDelete(null)}
                  style={{
                    padding: '10px 22px',
                    background: 'transparent',
                    border: '1px solid #333',
                    borderRadius: '8px',
                    color: '#666',
                    cursor: 'pointer',
                    fontSize: '13px',
                  }}
                >
                  Anulează
                </button>
                <button
                  onClick={() => handleDelete(confirmDelete)}
                  disabled={deleting === confirmDelete}
                  style={{
                    padding: '10px 22px',
                    background: 'rgba(255,77,77,0.1)',
                    border: '1px solid #ff4d4d',
                    borderRadius: '8px',
                    color: '#ff4d4d',
                    cursor: 'pointer',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    opacity: deleting === confirmDelete ? 0.6 : 1,
                  }}
                >
                  {deleting === confirmDelete ? 'Se șterge...' : 'Da, șterge'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default Challenges;
