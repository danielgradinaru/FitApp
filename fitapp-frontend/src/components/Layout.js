// src/components/Layout.js
import React, { useState, useEffect, useContext } from 'react';
import { motion } from 'framer-motion';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { getUserProfile } from '../api';
import { supabase } from '../lib/supabase';
import {
  FaHome,
  FaHistory,
  FaSignOutAlt,
  FaDumbbell,
  FaChartBar,
  FaUserAstronaut,
  FaFire,
  FaBolt,
  FaTrophy,
} from 'react-icons/fa';

const Layout = ({ children }) => {
  const { logout, user } = useContext(AuthContext);
  const location = useLocation();
  const navigate = useNavigate();

  const [hovered, setHovered] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  const [profile, setProfile] = useState({
    full_name: 'User',
    email: '',
    avatar_path: '',
    xp: 0,
    level: 1,
    rank: 'Novice',
    streak: 0,
    next_level_xp: 300,
  });

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const res = await getUserProfile();
        const data = res.data || {};

        const {
          data: { user: authUser },
        } = await supabase.auth.getUser();

        let avatarPath = '';
        if (authUser?.id) {
          const { data: profileRow, error: profileError } = await supabase
            .from('profiles')
            .select('avatar_path')
            .eq('id', authUser.id)
            .single();

          if (!profileError) {
            avatarPath = profileRow?.avatar_path || '';
          }
        }

        const authMeta = data.user_metadata || {};
        const fallbackEmail = data.email || user?.email || '';
        const fallbackFullName =
          data.full_name ||
          authMeta.full_name ||
          authMeta.name ||
          user?.user_metadata?.full_name ||
          user?.user_metadata?.name ||
          (fallbackEmail ? fallbackEmail.split('@')[0] : 'User');

        setProfile({
          full_name: fallbackFullName,
          email: fallbackEmail,
          avatar_path: avatarPath,
          xp: data.xp ?? data.total_xp ?? 0,
          level: data.level ?? 1,
          rank: data.rank ?? 'Novice',
          streak: data.streak ?? data.streak_days ?? 0,
          next_level_xp: data.next_level_xp ?? 300,
        });
      } catch (err) {
        console.error('Eroare la incarcare profil:', err);

        const fallbackEmail = user?.email || '';
        const fallbackFullName =
          user?.user_metadata?.full_name ||
          user?.user_metadata?.name ||
          (fallbackEmail ? fallbackEmail.split('@')[0] : 'User');

        setProfile((prev) => ({
          ...prev,
          full_name: fallbackFullName,
          email: fallbackEmail,
        }));
      }
    };

    loadProfile();

    const updateMouse = (e) => setMousePosition({ x: e.clientX, y: e.clientY });
    window.addEventListener('mousemove', updateMouse);

    return () => window.removeEventListener('mousemove', updateMouse);
  }, [location, user]);

  const handleLogout = async () => {
    await logout();
    navigate('/', { replace: true });
  };

  const handleProfileClick = () => {
    navigate('/profile');
  };

  const progressPercent =
    profile.next_level_xp > 0
      ? Math.min(100, ((profile.xp % profile.next_level_xp) / profile.next_level_xp) * 100)
      : 0;

  const menuItems = [
    { path: '/home', name: 'Acasa', icon: <FaHome /> },
    { path: '/progress', name: 'Statistici', icon: <FaChartBar /> },
    { path: '/history', name: 'Istoric', icon: <FaHistory /> },
    { path: '/challenges', name: 'Provocări', icon: <FaTrophy /> },
  ];

  const getAvatarUrl = (avatarPath) => {
    if (!avatarPath) return '';
    const { data } = supabase.storage.from('avatars').getPublicUrl(avatarPath);
    return data?.publicUrl || '';
  };

  const sidebarAvatarUrl = getAvatarUrl(profile.avatar_path);

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        background: '#050505',
        color: '#fff',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          zIndex: 0,
          background: `radial-gradient(600px at ${mousePosition.x}px ${mousePosition.y}px, rgba(0, 243, 255, 0.05), transparent 80%)`,
        }}
      />

      <motion.div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        animate={{ width: hovered ? 260 : 80 }}
        style={{
          background: 'rgba(10, 10, 15, 0.95)',
          borderRight: '1px solid #333',
          zIndex: 100,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '20px 0',
          height: '100vh',
          position: 'sticky',
          top: 0,
          overflow: 'hidden',
          backdropFilter: 'blur(10px)',
        }}
      >
        <div>
          <div
            style={{
              height: '60px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '30px',
            }}
          >
            <FaDumbbell
              size={32}
              color="var(--neon-cyan)"
              style={{ filter: 'drop-shadow(0 0 5px var(--neon-cyan))' }}
            />
            {hovered && (
              <motion.span
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 }}
                style={{
                  marginLeft: '12px',
                  fontFamily: 'Orbitron',
                  fontWeight: 'bold',
                  fontSize: '18px',
                  letterSpacing: '2px',
                }}
              >
                FITAPP
              </motion.span>
            )}
          </div>

          <div
            onClick={handleProfileClick}
            style={{
              padding: '0 10px',
              marginBottom: '40px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              cursor: 'pointer',
            }}
            title="Deschide profilul"
          >
            <div
              style={{
                width: hovered ? '60px' : '40px',
                height: hovered ? '60px' : '40px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, #2a2a35, #1a1a20)',
                border: '1px solid var(--neon-purple)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 15px rgba(188, 19, 254, 0.2)',
                transition: 'all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1)',
                overflow: 'hidden',
              }}
            >
              {sidebarAvatarUrl ? (
                <img
                  src={sidebarAvatarUrl}
                  alt="Avatar profil"
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                  }}
                />
              ) : (
                <FaUserAstronaut size={hovered ? 28 : 20} color="#fff" />
              )}
            </div>

            {hovered && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                style={{ width: '100%', marginTop: '15px', textAlign: 'center' }}
              >
                <div
                  style={{
                    fontSize: '15px',
                    fontWeight: 'bold',
                    color: '#fff',
                    marginBottom: '2px',
                  }}
                >
                  {profile.full_name}
                </div>

                <div
                  style={{
                    fontSize: '11px',
                    color: '#888',
                    textTransform: 'uppercase',
                    letterSpacing: '1px',
                    marginBottom: '12px',
                  }}
                >
                  {profile.rank}
                </div>

                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'center',
                    gap: '8px',
                    marginBottom: '15px',
                  }}
                >
                  <div
                    style={{
                      background: 'rgba(0, 255, 153, 0.1)',
                      border: '1px solid rgba(0, 255, 153, 0.3)',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      color: '#00ff99',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                  >
                    <FaFire style={{ marginRight: '4px' }} /> {profile.streak} Zile
                  </div>

                  <div
                    style={{
                      background: 'rgba(0, 243, 255, 0.1)',
                      border: '1px solid rgba(0, 243, 255, 0.3)',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '11px',
                      color: 'var(--neon-cyan)',
                      display: 'flex',
                      alignItems: 'center',
                    }}
                  >
                    <FaBolt style={{ marginRight: '4px' }} /> Lvl {profile.level}
                  </div>
                </div>

                <div style={{ width: '85%', margin: '0 auto' }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '9px',
                      color: '#666',
                      marginBottom: '4px',
                    }}
                  >
                    <span>XP</span>
                    <span>{Math.floor(progressPercent)}%</span>
                  </div>

                  <div
                    style={{
                      width: '100%',
                      height: '4px',
                      background: '#333',
                      borderRadius: '2px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${progressPercent}%`,
                        height: '100%',
                        background: 'linear-gradient(90deg, var(--neon-cyan), var(--neon-purple))',
                        boxShadow: '0 0 10px var(--neon-cyan)',
                        transition: 'width 0.5s ease',
                      }}
                    />
                  </div>
                </div>
              </motion.div>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {menuItems.map((item) => {
              const active = location.pathname === item.path;

              return (
                <Link to={item.path} key={item.path} style={{ textDecoration: 'none' }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      padding: '12px 26px',
                      color: active ? '#fff' : '#888',
                      background: active
                        ? 'linear-gradient(90deg, rgba(0, 243, 255, 0.1), transparent)'
                        : 'transparent',
                      borderLeft: active
                        ? '3px solid var(--neon-cyan)'
                        : '3px solid transparent',
                      transition: 'all 0.2s',
                      whiteSpace: 'nowrap',
                      cursor: 'pointer',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '18px',
                        minWidth: '28px',
                        color: active ? 'var(--neon-cyan)' : 'inherit',
                      }}
                    >
                      {item.icon}
                    </span>

                    {hovered && (
                      <motion.span
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        style={{
                          marginLeft: '12px',
                          fontSize: '14px',
                          fontWeight: active ? 'bold' : 'normal',
                        }}
                      >
                        {item.name}
                      </motion.span>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>

        <button
          onClick={handleLogout}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#ff4d4d',
            padding: '20px 26px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: hovered ? 'flex-start' : 'center',
            transition: '0.2s',
          }}
        >
          <FaSignOutAlt size={20} style={{ minWidth: '28px' }} />
          {hovered && <span style={{ marginLeft: '12px', fontSize: '14px' }}>Deconectare</span>}
        </button>
      </motion.div>

      <div
        style={{
          flex: 1,
          padding: '40px',
          overflowY: 'auto',
          zIndex: 1,
          position: 'relative',
        }}
      >
        {children}
      </div>
    </div>
  );
};

export default Layout; 