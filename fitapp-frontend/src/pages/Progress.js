// src/pages/Progress.js
import React, { useContext, useEffect, useState } from 'react';
import { getHistory, getUserProfile } from '../api';
import { motion } from 'framer-motion';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import Calendar from 'react-calendar';
import { format, isSameDay, parseISO } from 'date-fns';
import {
  FaTrophy,
  FaChartLine,
  FaListOl,
  FaCheckCircle,
  FaLock,
  FaUsers,
  FaGlobeEurope,
  FaGlobe,
} from 'react-icons/fa';
import { AuthContext } from '../context/AuthContext';
import { supabase } from '../lib/supabase';
import '../Calendar.css';

const ALL_BADGES = [
  { id: 'b_first', name: 'Inceputul', desc: 'Primul antrenament salvat', icon: '🌱' },
  { id: 'b_perf', name: 'Perfectionist', desc: 'Antrenament cu scor > 90%', icon: '💎' },
  { id: 'b_streak3', name: 'Incalzirea', desc: 'Streak de 3 zile', icon: '🔥' },
  { id: 'b_streak7', name: 'De Neoprit', desc: 'Streak de 7 zile', icon: '🚀' },
  { id: 'b_streak30', name: 'Discipol', desc: 'Streak de 30 zile', icon: '🧘' },
  { id: 'b_rep_master', name: 'Rep Master', desc: '20+ repetari intr-o sesiune', icon: '🏋️' },
  { id: 'b_sniper', name: 'Sniper', desc: 'Toate repetarile > 80%', icon: '🎯' },
  { id: 'b_night', name: 'Night Owl', desc: 'Antrenament noaptea (22-04)', icon: '🦉' },
  { id: 'b_morning', name: 'Early Bird', desc: 'Antrenament dimineata (05-09)', icon: '🌅' },
  { id: 'b_lvl10', name: 'Veteran', desc: 'Atins nivelul 10', icon: '🎖️' },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div
        style={{
          backgroundColor: '#0a0a0f',
          border: '1px solid var(--neon-cyan)',
          padding: '10px',
          borderRadius: '5px',
        }}
      >
        <p style={{ color: '#ccc', margin: 0 }}>{label}</p>
        <p style={{ color: 'var(--neon-cyan)', margin: 0, fontWeight: 'bold' }}>
          Scor: {payload[0].value}%
        </p>
      </div>
    );
  }
  return null;
};

const StatCard = ({ icon, title, value, color }) => (
  <div
    className="cyber-card"
    style={{
      padding: '20px',
      display: 'flex',
      alignItems: 'center',
      gap: '15px',
      borderLeft: `4px solid ${color}`,
    }}
  >
    <div
      style={{
        padding: '12px',
        background: `${color}20`,
        borderRadius: '8px',
        color: color,
        fontSize: '1.5rem',
      }}
    >
      {icon}
    </div>
    <div>
      <p style={{ margin: 0, color: '#888', fontSize: '0.9rem' }}>{title}</p>
      <h2 style={{ margin: '5px 0 0 0', fontFamily: 'Orbitron', fontSize: '1.8rem' }}>{value}</h2>
    </div>
  </div>
);

const LeaderboardCard = ({ title, icon, rows }) => (
  <div className="cyber-card" style={{ padding: '20px' }}>
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        marginBottom: '16px',
        color: 'var(--neon-cyan)',
      }}
    >
      {icon}
      <h3 style={{ margin: 0, fontFamily: 'Orbitron' }}>{title}</h3>
    </div>

    {!rows.length ? (
      <div style={{ color: '#666' }}>Nu exista date.</div>
    ) : (
      <div style={{ display: 'grid', gap: '10px' }}>
        {rows.map((row, index) => (
          <div
            key={row.id || `${title}-${index}`}
            style={{
              background: 'rgba(255,255,255,0.03)',
              padding: '12px',
              borderRadius: '10px',
              border: '1px solid rgba(255,255,255,0.08)',
              display: 'flex',
              justifyContent: 'space-between',
              gap: '10px',
            }}
          >
            <div>
              <div style={{ color: '#fff', fontWeight: 'bold' }}>
                #{index + 1} {row.full_name || row.username || 'User'}
              </div>
              <div style={{ color: '#888', fontSize: '12px' }}>
                @{row.username || 'fara_username'} {row.country ? `• ${row.country}` : ''}
              </div>
            </div>
            <div style={{ color: 'var(--neon-purple)', fontWeight: 'bold' }}>
              {row.total_xp ?? 0} XP
            </div>
          </div>
        ))}
      </div>
    )}
  </div>
);

const Progress = () => {
  const { user } = useContext(AuthContext);

  const [fullHistory, setFullHistory] = useState([]);
  const [chartData, setChartData] = useState([]);
  const [selectedExercise, setSelectedExercise] = useState('Toate');
  const [stats, setStats] = useState({ best: 0, avg: 0, count: 0 });

  const [date, setDate] = useState(new Date());
  const [dayWorkouts, setDayWorkouts] = useState([]);

  const [myBadges, setMyBadges] = useState([]);
  const [myProfile, setMyProfile] = useState(null);

  const [friendsTop, setFriendsTop] = useState([]);
  const [countryTop, setCountryTop] = useState([]);
  const [globalTop, setGlobalTop] = useState([]);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    processChartData();
  }, [selectedExercise, fullHistory]);

  useEffect(() => {
    filterDayWorkouts();
  }, [date, fullHistory]);

  const loadLeaderboards = async (authUserId, currentProfile) => {
    const { data: globalData, error: globalError } = await supabase
      .from('profiles')
      .select('id, username, full_name, country, total_xp')
      .order('total_xp', { ascending: false })
      .limit(10);

    if (!globalError) {
      setGlobalTop(globalData || []);
    }

    if (currentProfile?.country) {
      const { data: countryData, error: countryError } = await supabase
        .from('profiles')
        .select('id, username, full_name, country, total_xp')
        .eq('country', currentProfile.country)
        .order('total_xp', { ascending: false })
        .limit(10);

      if (!countryError) {
        setCountryTop(countryData || []);
      }
    } else {
      setCountryTop([]);
    }

    const { data: relations, error: relationsError } = await supabase
      .from('friend_requests')
      .select('*')
      .or(`sender_id.eq.${authUserId},receiver_id.eq.${authUserId}`);

    if (!relationsError) {
      const accepted = (relations || []).filter((r) => r.status === 'accepted');
      const friendIds = accepted.map((r) =>
        r.sender_id === authUserId ? r.receiver_id : r.sender_id
      );

      const idsForTop = [authUserId, ...friendIds];

      if (idsForTop.length > 0) {
        const { data: friendsData, error: friendsError } = await supabase
          .from('profiles')
          .select('id, username, full_name, country, total_xp')
          .in('id', idsForTop)
          .order('total_xp', { ascending: false });

        if (!friendsError) {
          setFriendsTop(friendsData || []);
        }
      } else {
        setFriendsTop([]);
      }
    }
  };

  const loadData = async () => {
    try {
      const resHistory = await getHistory();
      const data = Array.isArray(resHistory.data) ? resHistory.data : [];
      data.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
      setFullHistory(data);

      const resProfile = await getUserProfile();
      setMyBadges(resProfile.data.badges || []);

      const {
        data: { user: authUser },
      } = await supabase.auth.getUser();

      if (authUser) {
        const { data: profileData, error: profileError } = await supabase
          .from('profiles')
          .select('*')
          .eq('id', authUser.id)
          .single();

        if (!profileError) {
          setMyProfile(profileData);
          await loadLeaderboards(authUser.id, profileData);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const processChartData = () => {
    let data = fullHistory;

    if (selectedExercise !== 'Toate') {
      data = fullHistory.filter((item) => item.exercise === selectedExercise);
    }

    if (data.length > 0) {
      const scores = data.map((d) => Number(d.avg_score) || 0);
      const max = Math.max(...scores);
      const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
      setStats({ best: max, avg: Math.round(avg), count: data.length });
    } else {
      setStats({ best: 0, avg: 0, count: 0 });
    }

    const formatted = data.map((item) => {
      const d = new Date(item.created_at);
      return {
        ...item,
        displayDate: `${d.getDate()}/${d.getMonth() + 1} ${d.getHours()}:${String(
          d.getMinutes()
        ).padStart(2, '0')}`,
        avg_score: Math.round(Number(item.avg_score) || 0),
      };
    });

    setChartData(formatted);
  };

  const filterDayWorkouts = () => {
    const workouts = fullHistory.filter((item) => isSameDay(parseISO(item.created_at), date));
    setDayWorkouts(workouts.reverse());
  };

  const tileClassName = ({ date, view }) => {
    if (view === 'month') {
      if (fullHistory.some((item) => isSameDay(parseISO(item.created_at), date))) {
        return 'workout-day';
      }
    }
    return null;
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '30px',
        }}
      >
        <h2
          className="glow-text"
          style={{ fontFamily: 'Orbitron', color: 'var(--neon-purple)', margin: 0 }}
        >
          STATISTICI
        </h2>
        <select
          className="cyber-input"
          value={selectedExercise}
          onChange={(e) => setSelectedExercise(e.target.value)}
          style={{ width: '200px' }}
        >
          <option>Toate</option>
          <option>Genuflexiune</option>
          <option>Flotare</option>
          <option>Deadlift</option>
          <option>Fandare</option>
          <option>Abdomene</option>
          <option>Tractiuni</option>
          <option>Bench Press</option>
          <option>Mountain Climbers</option>
          <option>Plank</option>
        </select>
      </div>

      {myProfile && (
        <div
          className="cyber-card"
          style={{
            padding: '16px 20px',
            marginBottom: '20px',
            display: 'flex',
            gap: '12px',
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          <div style={{ color: '#fff', fontWeight: 'bold' }}>
            XP curent: <span style={{ color: 'var(--neon-purple)' }}>{myProfile.total_xp ?? 0}</span>
          </div>
          <div style={{ color: '#fff' }}>
            Nivel: <span style={{ color: 'var(--neon-cyan)' }}>{myProfile.level ?? 1}</span>
          </div>
          <div style={{ color: '#fff' }}>
            Tara: <span style={{ color: '#00ff99' }}>{myProfile.country || '-'}</span>
          </div>
        </div>
      )}

      <motion.div
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="cyber-card"
        style={{
          padding: '25px',
          marginBottom: '40px',
          background: 'linear-gradient(180deg, rgba(20,20,30,0.9), rgba(10,10,15,0.9))',
        }}
      >
        <h3
          style={{
            margin: '0 0 25px 0',
            color: 'gold',
            fontFamily: 'Orbitron',
            textAlign: 'center',
            fontSize: '1.5rem',
            textShadow: '0 0 10px rgba(255,215,0,0.3)',
          }}
        >
          🏆 SALA DE TROFEE
        </h3>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
            gap: '15px',
          }}
        >
          {ALL_BADGES.map((badge) => {
            const isUnlocked = myBadges.includes(badge.id);
            return (
              <div
                key={badge.id}
                style={{
                  background: isUnlocked ? 'rgba(255, 215, 0, 0.08)' : 'rgba(255,255,255,0.02)',
                  border: isUnlocked ? '1px solid gold' : '1px solid #333',
                  borderRadius: '12px',
                  padding: '15px',
                  textAlign: 'center',
                  opacity: isUnlocked ? 1 : 0.5,
                  filter: isUnlocked ? 'none' : 'grayscale(100%) blur(0.5px)',
                  position: 'relative',
                  transition: '0.3s',
                }}
              >
                <div style={{ fontSize: '2.5rem', marginBottom: '10px' }}>{badge.icon}</div>
                <div
                  style={{
                    fontWeight: 'bold',
                    color: isUnlocked ? 'gold' : '#888',
                    marginBottom: '5px',
                  }}
                >
                  {badge.name}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#666', lineHeight: '1.2' }}>
                  {badge.desc}
                </div>

                {!isUnlocked && (
                  <div style={{ position: 'absolute', top: 10, right: 10, color: '#555' }}>
                    <FaLock />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </motion.div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: '20px',
          marginBottom: '40px',
        }}
      >
        <LeaderboardCard title="Top prieteni" icon={<FaUsers />} rows={friendsTop} />
        <LeaderboardCard title="Top tara" icon={<FaGlobeEurope />} rows={countryTop} />
        <LeaderboardCard title="Top global" icon={<FaGlobe />} rows={globalTop} />
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.5fr 1fr',
          gap: '30px',
          marginBottom: '40px',
        }}
      >
        <motion.div
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          className="cyber-card"
          style={{ padding: '20px' }}
        >
          <h3 style={{ margin: '0 0 20px 0', color: '#fff', fontFamily: 'Orbitron' }}>
            CALENDAR
          </h3>
          <Calendar onChange={setDate} value={date} tileClassName={tileClassName} />
        </motion.div>

        <motion.div
          initial={{ x: 20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          className="cyber-card"
          style={{ padding: '20px', display: 'flex', flexDirection: 'column' }}
        >
          <h3
            style={{
              margin: '0 0 15px 0',
              color: 'var(--neon-cyan)',
              fontFamily: 'Orbitron',
              borderBottom: '1px solid #333',
              paddingBottom: '10px',
            }}
          >
            {format(date, 'dd MMMM yyyy')}
          </h3>
          <div style={{ flex: 1, overflowY: 'auto', maxHeight: '350px', paddingRight: '5px' }}>
            {dayWorkouts.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#666', marginTop: '50px' }}>
                <p>Nicio activitate.</p>
              </div>
            ) : (
              dayWorkouts.map((workout) => (
                <div
                  key={workout.id}
                  style={{
                    background: 'rgba(255,255,255,0.03)',
                    marginBottom: '10px',
                    padding: '12px',
                    borderRadius: '8px',
                    borderLeft: `3px solid ${workout.avg_score >= 80 ? '#00ff99' : 'orange'}`,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 'bold', color: '#fff' }}>{workout.exercise}</span>
                    <span
                      style={{
                        color: workout.avg_score >= 80 ? '#00ff99' : 'orange',
                        fontWeight: 'bold',
                      }}
                    >
                      {parseInt(workout.avg_score, 10)}%
                    </span>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#888', marginTop: '5px' }}>
                    {new Date(workout.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}{' '}
                    • <FaCheckCircle style={{ display: 'inline', fontSize: '10px' }} /> Salvat
                  </div>
                </div>
              ))
            )}
          </div>
        </motion.div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '20px',
          marginBottom: '40px',
        }}
      >
        <StatCard icon={<FaChartLine />} title="Scor Mediu Global" value={`${stats.avg}%`} color="#00E5FF" />
        <StatCard icon={<FaTrophy />} title="Cel mai bun scor" value={`${stats.best}%`} color="#00FF99" />
        <StatCard icon={<FaListOl />} title="Total Sesiuni" value={stats.count} color="#BC13FE" />
      </div>

      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        className="cyber-card"
        style={{ padding: '30px', height: '400px' }}
      >
        <h3 style={{ fontFamily: 'Orbitron', marginBottom: '20px', color: '#ccc' }}>
          Grafic Evolutie - {selectedExercise}
        </h3>

        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--neon-cyan)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--neon-cyan)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="displayDate" stroke="#666" />
              <YAxis stroke="#666" domain={[0, 100]} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="avg_score"
                stroke="var(--neon-cyan)"
                strokeWidth={3}
                fillOpacity={1}
                fill="url(#colorScore)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div
            style={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#666',
            }}
          >
            Nu exista date suficiente pentru grafic.
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default Progress;
