import React, { useContext, useEffect, useMemo, useState } from 'react';
import { AuthContext } from '../context/AuthContext';
import { supabase } from '../lib/supabase';

const cardStyle = {
  background: 'rgba(10, 10, 15, 0.92)',
  border: '1px solid rgba(0, 243, 255, 0.15)',
  borderRadius: '16px',
  padding: '24px',
  boxShadow: '0 0 20px rgba(0, 243, 255, 0.06)',
};

const labelStyle = {
  display: 'block',
  fontSize: '12px',
  color: 'var(--neon-cyan)',
  marginBottom: '8px',
  letterSpacing: '0.8px',
  textTransform: 'uppercase',
};

const inputStyle = {
  width: '100%',
  padding: '12px 14px',
  borderRadius: '10px',
  border: '1px solid rgba(255,255,255,0.12)',
  background: 'rgba(255,255,255,0.04)',
  color: '#fff',
  outline: 'none',
  boxSizing: 'border-box',
};

const buttonStyle = {
  padding: '12px 18px',
  borderRadius: '10px',
  border: '1px solid var(--neon-cyan)',
  background: 'transparent',
  color: 'var(--neon-cyan)',
  cursor: 'pointer',
  fontFamily: 'inherit',
};

const primaryButtonStyle = {
  ...buttonStyle,
  background: 'rgba(0, 243, 255, 0.08)',
};

const secondaryButtonStyle = {
  ...buttonStyle,
  border: '1px solid rgba(255,255,255,0.18)',
  color: '#ddd',
};

const dangerButtonStyle = {
  ...buttonStyle,
  border: '1px solid rgba(255, 107, 107, 0.35)',
  color: '#ff6b6b',
};

const badgeStyle = {
  padding: '8px 12px',
  borderRadius: '10px',
  fontSize: '13px',
  fontWeight: 600,
  display: 'inline-flex',
  alignItems: 'center',
};

const detailItemStyle = {
  padding: '14px 0',
  borderBottom: '1px solid rgba(255,255,255,0.08)',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: '16px',
};

const detailLabelStyle = {
  color: 'var(--neon-cyan)',
  fontSize: '12px',
  textTransform: 'uppercase',
  letterSpacing: '0.8px',
  minWidth: '140px',
};

const detailValueStyle = {
  color: '#fff',
  fontSize: '15px',
  textAlign: 'right',
  flex: 1,
  lineHeight: 1.5,
  wordBreak: 'break-word',
};

const softPanelStyle = {
  padding: '14px 16px',
  borderRadius: '14px',
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid rgba(255,255,255,0.06)',
};

const getPublicAvatarUrl = (avatarPath) => {
  if (!avatarPath) return '';
  const { data } = supabase.storage.from('avatars').getPublicUrl(avatarPath);
  return data?.publicUrl || '';
};

const Profile = () => {
  const { user } = useContext(AuthContext);

  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({
    username: '',
    full_name: '',
    bio: '',
    weight_kg: '',
    height_cm: '',
    country: '',
    birth_date: '',
    avatar_path: '',
    total_xp: 0,
    level: 1,
    streak_days: 0,
  });

  const [editMode, setEditMode] = useState(false);
  const [avatarFile, setAvatarFile] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const [friends, setFriends] = useState([]);
  const [incomingRequests, setIncomingRequests] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [friendActionLoading, setFriendActionLoading] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);

  const avatarUrl = useMemo(() => {
    if (avatarPreview) return avatarPreview;
    return getPublicAvatarUrl(form.avatar_path);
  }, [form.avatar_path, avatarPreview]);

  const loadFriendsData = async (authUserId) => {
    const { data: relations, error: relationsError } = await supabase
      .from('friend_requests')
      .select('*')
      .or(`sender_id.eq.${authUserId},receiver_id.eq.${authUserId}`);

    if (relationsError) throw relationsError;

    const accepted = (relations || []).filter((r) => r.status === 'accepted');
    const incoming = (relations || []).filter(
      (r) => r.status === 'pending' && r.receiver_id === authUserId
    );

    const friendIds = accepted.map((r) =>
      r.sender_id === authUserId ? r.receiver_id : r.sender_id
    );

    let friendsData = [];
    if (friendIds.length > 0) {
      const { data: profilesData, error: friendsError } = await supabase
        .from('profiles')
        .select('id, username, full_name, avatar_path, country, total_xp, level, streak_days, bio')
        .in('id', friendIds)
        .order('total_xp', { ascending: false });

      if (friendsError) throw friendsError;
      friendsData = profilesData || [];
    }

    let incomingWithProfiles = [];
    if (incoming.length > 0) {
      const senderIds = incoming.map((r) => r.sender_id);
      const { data: senders, error: sendersError } = await supabase
        .from('profiles')
        .select('id, username, full_name, avatar_path, country, total_xp, level, streak_days, bio')
        .in('id', senderIds);

      if (sendersError) throw sendersError;

      incomingWithProfiles = incoming.map((req) => ({
        ...req,
        sender_profile: (senders || []).find((p) => p.id === req.sender_id) || null,
      }));
    }

    setFriends(friendsData);
    setIncomingRequests(incomingWithProfiles);
  };

  const loadProfile = async () => {
    setLoading(true);
    setError('');
    setMessage('');

    try {
      const {
        data: { user: authUser },
        error: authError,
      } = await supabase.auth.getUser();

      if (authError) throw authError;
      if (!authUser) throw new Error('Nu exista utilizator autentificat.');

      const { data, error: profileError } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', authUser.id)
        .single();

      if (profileError) throw profileError;

      setProfile(data);
      setForm({
        username: data?.username || '',
        full_name: data?.full_name || '',
        bio: data?.bio || '',
        weight_kg: data?.weight_kg ?? '',
        height_cm: data?.height_cm ?? '',
        country: data?.country || '',
        birth_date: data?.birth_date || '',
        avatar_path: data?.avatar_path || '',
        total_xp: data?.total_xp ?? 0,
        level: data?.level ?? 1,
        streak_days: data?.streak_days ?? 0,
      });

      await loadFriendsData(authUser.id);
    } catch (err) {
      console.error('Eroare la incarcare profil:', err);
      setError(err?.message || 'Nu am putut incarca profilul.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, [user]);

  useEffect(() => {
    const runSearch = async () => {
      const term = searchTerm.trim();
      if (!term || term.length < 2) {
        setSearchResults([]);
        return;
      }

      try {
        setSearchLoading(true);

        const {
          data: { user: authUser },
        } = await supabase.auth.getUser();

        if (!authUser) return;

        const { data, error: searchError } = await supabase
          .from('profiles')
          .select('id, username, full_name, avatar_path, country, total_xp, level, streak_days, bio')
          .or(`username.ilike.%${term}%,full_name.ilike.%${term}%`)
          .neq('id', authUser.id)
          .limit(10);

        if (searchError) throw searchError;

        setSearchResults(data || []);
      } catch (err) {
        console.error('Eroare la cautare utilizatori:', err);
      } finally {
        setSearchLoading(false);
      }
    };

    const t = setTimeout(runSearch, 300);
    return () => clearTimeout(t);
  }, [searchTerm]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleAvatarChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(file));
  };

  const handleCancel = () => {
    if (!profile) return;

    setEditMode(false);
    setMessage('');
    setError('');
    setAvatarFile(null);
    setAvatarPreview('');

    setForm({
      username: profile?.username || '',
      full_name: profile?.full_name || '',
      bio: profile?.bio || '',
      weight_kg: profile?.weight_kg ?? '',
      height_cm: profile?.height_cm ?? '',
      country: profile?.country || '',
      birth_date: profile?.birth_date || '',
      avatar_path: profile?.avatar_path || '',
      total_xp: profile?.total_xp ?? 0,
      level: profile?.level ?? 1,
      streak_days: profile?.streak_days ?? 0,
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setMessage('');

    try {
      const {
        data: { user: authUser },
        error: authError,
      } = await supabase.auth.getUser();

      if (authError) throw authError;
      if (!authUser) throw new Error('Nu exista utilizator autentificat.');

      let avatarPath = form.avatar_path;

      if (avatarFile) {
        const ext = avatarFile.name.split('.').pop();
        avatarPath = `${authUser.id}/avatar-${Date.now()}.${ext}`;

        const { error: uploadError } = await supabase.storage
          .from('avatars')
          .upload(avatarPath, avatarFile, { upsert: true });

        if (uploadError) throw uploadError;
      }

      const payload = {
        username: form.username || null,
        full_name: form.full_name || null,
        bio: form.bio || null,
        weight_kg: form.weight_kg === '' ? null : Number(form.weight_kg),
        height_cm: form.height_cm === '' ? null : Number(form.height_cm),
        country: form.country || null,
        birth_date: form.birth_date || null,
        avatar_path: avatarPath || null,
      };

      const { data: updated, error: updateError } = await supabase
        .from('profiles')
        .update(payload)
        .eq('id', authUser.id)
        .select()
        .single();

      if (updateError) throw updateError;

      setProfile(updated);
      setForm({
        username: updated?.username || '',
        full_name: updated?.full_name || '',
        bio: updated?.bio || '',
        weight_kg: updated?.weight_kg ?? '',
        height_cm: updated?.height_cm ?? '',
        country: updated?.country || '',
        birth_date: updated?.birth_date || '',
        avatar_path: updated?.avatar_path || '',
        total_xp: updated?.total_xp ?? 0,
        level: updated?.level ?? 1,
        streak_days: updated?.streak_days ?? 0,
      });

      setAvatarFile(null);
      setAvatarPreview('');
      setEditMode(false);
      setMessage('Profilul a fost actualizat.');
    } catch (err) {
      console.error('Eroare la salvare profil:', err);
      setError(err?.message || 'Nu am putut salva profilul.');
    } finally {
      setSaving(false);
    }
  };

  const sendFriendRequest = async (targetUserId) => {
    try {
      setFriendActionLoading(targetUserId);

      const {
        data: { user: authUser },
      } = await supabase.auth.getUser();

      if (!authUser) throw new Error('Nu exista utilizator autentificat.');

      const { data: existing, error: existingError } = await supabase
        .from('friend_requests')
        .select('*')
        .or(
          `and(sender_id.eq.${authUser.id},receiver_id.eq.${targetUserId}),and(sender_id.eq.${targetUserId},receiver_id.eq.${authUser.id})`
        );

      if (existingError) throw existingError;

      if ((existing || []).length > 0) {
        setMessage('Exista deja o relatie sau o cerere intre voi.');
        return;
      }

      const { error: insertError } = await supabase.from('friend_requests').insert({
        sender_id: authUser.id,
        receiver_id: targetUserId,
        status: 'pending',
      });

      if (insertError) throw insertError;

      setMessage('Cererea de prietenie a fost trimisa.');
    } catch (err) {
      console.error('Eroare la trimitere cerere:', err);
      setError(err?.message || 'Nu am putut trimite cererea.');
    } finally {
      setFriendActionLoading('');
    }
  };

  const respondToRequest = async (requestId, status) => {
    try {
      setFriendActionLoading(requestId);

      const { error: updateError } = await supabase
        .from('friend_requests')
        .update({ status })
        .eq('id', requestId);

      if (updateError) throw updateError;

      await loadProfile();
      setMessage(status === 'accepted' ? 'Cerere acceptata.' : 'Cerere respinsa.');
    } catch (err) {
      console.error('Eroare la actualizare cerere:', err);
      setError(err?.message || 'Nu am putut actualiza cererea.');
    } finally {
      setFriendActionLoading('');
    }
  };

  const removeFriend = async (friendId) => {
    try {
      setFriendActionLoading(friendId);

      const {
        data: { user: authUser },
      } = await supabase.auth.getUser();

      if (!authUser) throw new Error('Nu exista utilizator autentificat.');

      const { error: deleteError } = await supabase
        .from('friend_requests')
        .delete()
        .or(
          `and(sender_id.eq.${authUser.id},receiver_id.eq.${friendId},status.eq.accepted),and(sender_id.eq.${friendId},receiver_id.eq.${authUser.id},status.eq.accepted)`
        );

      if (deleteError) throw deleteError;

      if (selectedUser?.id === friendId) {
        setSelectedUser(null);
      }

      await loadProfile();
      setMessage('Prietenul a fost sters din lista.');
    } catch (err) {
      console.error('Eroare la stergere prieten:', err);
      setError(err?.message || 'Nu am putut sterge prietenul.');
    } finally {
      setFriendActionLoading('');
    }
  };

  if (loading) {
    return (
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <h2 className="glow-text" style={{ fontFamily: 'Orbitron', color: 'var(--neon-cyan)' }}>
          PROFILUL MEU
        </h2>
        <div className="cyber-card" style={{ padding: '24px', color: '#fff' }}>
          Se incarca profilul...
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <h2
        className="glow-text"
        style={{
          fontFamily: 'Orbitron',
          color: 'var(--neon-cyan)',
          marginBottom: '20px',
        }}
      >
        PROFILUL MEU
      </h2>

      {error && (
        <div
          className="cyber-card"
          style={{
            marginBottom: '16px',
            padding: '16px',
            color: '#ff6b6b',
            border: '1px solid rgba(255, 0, 0, 0.25)',
          }}
        >
          {error}
        </div>
      )}

      {message && (
        <div
          className="cyber-card"
          style={{
            marginBottom: '16px',
            padding: '16px',
            color: '#00ff99',
            border: '1px solid rgba(0, 255, 153, 0.25)',
          }}
        >
          {message}
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: editMode ? '320px 1fr' : '320px 1fr',
          gap: '20px',
          marginBottom: '20px',
        }}
      >
        <div style={cardStyle}>
          <div style={{ textAlign: 'center' }}>
            <div
              style={{
                width: '170px',
                height: '170px',
                margin: '0 auto 18px',
                borderRadius: '22px',
                border: '1px solid var(--neon-purple)',
                background: 'linear-gradient(135deg, #1e1e26, #111)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden',
                boxShadow: '0 0 18px rgba(188, 19, 254, 0.16)',
              }}
            >
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt="Avatar profil"
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <span style={{ fontSize: '54px' }}>👤</span>
              )}
            </div>

            <div style={{ fontSize: '26px', fontWeight: 'bold', color: '#fff', marginBottom: '8px' }}>
              {form.full_name || form.username || 'User'}
            </div>

            {form.username && (
              <div style={{ color: '#aaa', marginBottom: '14px' }}>@{form.username}</div>
            )}

            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                gap: '10px',
                flexWrap: 'wrap',
                marginBottom: '18px',
              }}
            >
              <div
                style={{
                  ...badgeStyle,
                  color: '#00ff99',
                  background: 'rgba(0,255,153,0.08)',
                  border: '1px solid rgba(0,255,153,0.24)',
                }}
              >
                {form.streak_days} zile streak
              </div>

              <div
                style={{
                  ...badgeStyle,
                  color: 'var(--neon-cyan)',
                  background: 'rgba(0,243,255,0.08)',
                  border: '1px solid rgba(0,243,255,0.24)',
                }}
              >
                Lvl {form.level}
              </div>

              <div
                style={{
                  ...badgeStyle,
                  color: 'var(--neon-purple)',
                  background: 'rgba(188,19,254,0.08)',
                  border: '1px solid rgba(188,19,254,0.24)',
                }}
              >
                XP {form.total_xp}
              </div>
            </div>

            {!editMode ? (
              <button style={primaryButtonStyle} onClick={() => setEditMode(true)}>
                Modifica profilul
              </button>
            ) : (
              <button style={secondaryButtonStyle} onClick={handleCancel} disabled={saving}>
                Inchide editarea
              </button>
            )}
          </div>
        </div>

        {!editMode && (
          <div style={cardStyle}>
            <h3 style={{ marginTop: 0, color: 'var(--neon-cyan)', marginBottom: '18px' }}>
              Detalii profil
            </h3>

            <div style={{ display: 'grid', gap: '2px' }}>
              <div style={detailItemStyle}>
                <div style={detailLabelStyle}>Nume complet</div>
                <div style={detailValueStyle}>{form.full_name || '-'}</div>
              </div>

              <div style={detailItemStyle}>
                <div style={detailLabelStyle}>Username</div>
                <div style={detailValueStyle}>@{form.username || '-'}</div>
              </div>

              <div style={detailItemStyle}>
                <div style={detailLabelStyle}>Bio</div>
                <div style={detailValueStyle}>{form.bio || 'Nu exista bio setat.'}</div>
              </div>

              <div style={detailItemStyle}>
                <div style={detailLabelStyle}>Greutate</div>
                <div style={detailValueStyle}>
                  {form.weight_kg ? `${form.weight_kg} kg` : '-'}
                </div>
              </div>

              <div style={detailItemStyle}>
                <div style={detailLabelStyle}>Inaltime</div>
                <div style={detailValueStyle}>
                  {form.height_cm ? `${form.height_cm} cm` : '-'}
                </div>
              </div>

              <div style={detailItemStyle}>
                <div style={detailLabelStyle}>Tara</div>
                <div style={detailValueStyle}>{form.country || '-'}</div>
              </div>

              <div style={{ ...detailItemStyle, borderBottom: 'none' }}>
                <div style={detailLabelStyle}>Data nasterii</div>
                <div style={detailValueStyle}>{form.birth_date || '-'}</div>
              </div>
            </div>

            <div
              style={{
                marginTop: '18px',
                display: 'flex',
                gap: '10px',
                flexWrap: 'wrap',
              }}
            >
              <div
                style={{
                  ...softPanelStyle,
                  color: '#00ff99',
                  border: '1px solid rgba(0,255,153,0.18)',
                  background: 'rgba(0,255,153,0.06)',
                }}
              >
                {form.streak_days} zile streak
              </div>

              <div
                style={{
                  ...softPanelStyle,
                  color: 'var(--neon-cyan)',
                  border: '1px solid rgba(0,243,255,0.18)',
                  background: 'rgba(0,243,255,0.06)',
                }}
              >
                Level {form.level}
              </div>

              <div
                style={{
                  ...softPanelStyle,
                  color: 'var(--neon-purple)',
                  border: '1px solid rgba(188,19,254,0.18)',
                  background: 'rgba(188,19,254,0.06)',
                }}
              >
                XP total {form.total_xp}
              </div>
            </div>
          </div>
        )}

        {editMode && (
          <div style={cardStyle}>
            <h3 style={{ marginTop: 0, color: 'var(--neon-purple)', marginBottom: '18px' }}>
              Editeaza profilul
            </h3>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr',
                gap: '16px',
              }}
            >
              <div>
                <label style={labelStyle}>Avatar</label>
                <input type="file" accept="image/*" onChange={handleAvatarChange} />
              </div>

              <div>
                <label style={labelStyle}>Nume complet</label>
                <input
                  name="full_name"
                  value={form.full_name}
                  onChange={handleChange}
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={labelStyle}>Username</label>
                <input
                  name="username"
                  value={form.username}
                  onChange={handleChange}
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={labelStyle}>Bio</label>
                <textarea
                  name="bio"
                  value={form.bio}
                  onChange={handleChange}
                  rows={4}
                  style={{ ...inputStyle, resize: 'vertical' }}
                />
              </div>

              <div>
                <label style={labelStyle}>Greutate (kg)</label>
                <input
                  name="weight_kg"
                  type="number"
                  step="0.1"
                  value={form.weight_kg}
                  onChange={handleChange}
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={labelStyle}>Inaltime (cm)</label>
                <input
                  name="height_cm"
                  type="number"
                  step="0.1"
                  value={form.height_cm}
                  onChange={handleChange}
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={labelStyle}>Tara</label>
                <input
                  name="country"
                  value={form.country}
                  onChange={handleChange}
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={labelStyle}>Data nasterii</label>
                <input
                  name="birth_date"
                  type="date"
                  value={form.birth_date || ''}
                  onChange={handleChange}
                  style={inputStyle}
                />
              </div>

              <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                <button style={primaryButtonStyle} onClick={handleSave} disabled={saving}>
                  {saving ? 'Se salveaza...' : 'Salveaza'}
                </button>
                <button style={secondaryButtonStyle} onClick={handleCancel} disabled={saving}>
                  Renunta
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '20px',
        }}
      >
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0, color: 'var(--neon-cyan)' }}>Prietenii mei</h3>

          {friends.length === 0 ? (
            <div style={{ color: '#999' }}>Nu ai inca prieteni adaugati.</div>
          ) : (
            <div style={{ display: 'grid', gap: '12px' }}>
              {friends.map((friend) => (
                <div
                  key={friend.id}
                  style={{
                    padding: '12px',
                    borderRadius: '12px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                    }}
                  >
                    <div
                      onClick={() => setSelectedUser(friend)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        flex: 1,
                        cursor: 'pointer',
                      }}
                    >
                      <div
                        style={{
                          width: '52px',
                          height: '52px',
                          borderRadius: '14px',
                          overflow: 'hidden',
                          background: '#111',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {friend.avatar_path ? (
                          <img
                            src={getPublicAvatarUrl(friend.avatar_path)}
                            alt="avatar"
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                        ) : (
                          <span>👤</span>
                        )}
                      </div>

                      <div style={{ flex: 1 }}>
                        <div style={{ color: '#fff', fontWeight: 'bold' }}>
                          {friend.full_name || friend.username || 'User'}
                        </div>
                        <div style={{ color: '#999', fontSize: '13px' }}>
                          @{friend.username || 'fara_username'}
                        </div>
                      </div>

                      <div style={{ color: 'var(--neon-purple)', fontWeight: 'bold' }}>
                        {friend.total_xp ?? 0} XP
                      </div>
                    </div>

                    <button
                      style={dangerButtonStyle}
                      disabled={friendActionLoading === friend.id}
                      onClick={() => removeFriend(friend.id)}
                    >
                      {friendActionLoading === friend.id ? 'Se sterge...' : 'Sterge prieten'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: '24px' }}>
            <h4 style={{ color: '#fff', marginBottom: '12px' }}>Cereri primite</h4>

            {incomingRequests.length === 0 ? (
              <div style={{ color: '#999' }}>Nu ai cereri noi.</div>
            ) : (
              <div style={{ display: 'grid', gap: '12px' }}>
                {incomingRequests.map((req) => (
                  <div
                    key={req.id}
                    style={{
                      padding: '12px',
                      borderRadius: '12px',
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}
                  >
                    <div style={{ color: '#fff', marginBottom: '10px' }}>
                      {req.sender_profile?.full_name || req.sender_profile?.username || 'User'}
                    </div>

                    <div style={{ display: 'flex', gap: '10px' }}>
                      <button
                        style={primaryButtonStyle}
                        disabled={friendActionLoading === req.id}
                        onClick={() => respondToRequest(req.id, 'accepted')}
                      >
                        Accepta
                      </button>
                      <button
                        style={dangerButtonStyle}
                        disabled={friendActionLoading === req.id}
                        onClick={() => respondToRequest(req.id, 'rejected')}
                      >
                        Respinge
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div style={cardStyle}>
          <h3 style={{ marginTop: 0, color: 'var(--neon-cyan)' }}>Cauta utilizatori</h3>

          <input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Cauta dupa username sau nume..."
            style={{ ...inputStyle, marginBottom: '16px' }}
          />

          {searchLoading ? (
            <div style={{ color: '#999' }}>Se cauta...</div>
          ) : searchResults.length === 0 ? (
            <div style={{ color: '#999' }}>
              Introdu cel putin 2 caractere pentru a cauta utilizatori.
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '12px' }}>
              {searchResults.map((result) => (
                <div
                  key={result.id}
                  style={{
                    padding: '12px',
                    borderRadius: '12px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                >
                  <div
                    onClick={() => setSelectedUser(result)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      cursor: 'pointer',
                    }}
                  >
                    <div
                      style={{
                        width: '52px',
                        height: '52px',
                        borderRadius: '14px',
                        overflow: 'hidden',
                        background: '#111',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {result.avatar_path ? (
                        <img
                          src={getPublicAvatarUrl(result.avatar_path)}
                          alt="avatar"
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      ) : (
                        <span>👤</span>
                      )}
                    </div>

                    <div style={{ flex: 1 }}>
                      <div style={{ color: '#fff', fontWeight: 'bold' }}>
                        {result.full_name || result.username || 'User'}
                      </div>
                      <div style={{ color: '#999', fontSize: '13px' }}>
                        @{result.username || 'fara_username'}
                      </div>
                    </div>

                    <div style={{ color: 'var(--neon-purple)', fontWeight: 'bold' }}>
                      {result.total_xp ?? 0} XP
                    </div>
                  </div>

                  <div style={{ marginTop: '12px' }}>
                    <button
                      style={primaryButtonStyle}
                      disabled={friendActionLoading === result.id}
                      onClick={() => sendFriendRequest(result.id)}
                    >
                      Trimite cerere de prietenie
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {selectedUser && (
            <div
              style={{
                marginTop: '24px',
                borderRadius: '18px',
                overflow: 'hidden',
                border: '1px solid rgba(188,19,254,0.24)',
                background:
                  'linear-gradient(180deg, rgba(188,19,254,0.10) 0%, rgba(255,255,255,0.03) 100%)',
              }}
            >
              <div
                style={{
                  height: '90px',
                  background:
                    'linear-gradient(90deg, rgba(0,243,255,0.18), rgba(188,19,254,0.18))',
                }}
              />

              <div style={{ padding: '0 18px 18px', marginTop: '-34px' }}>
                <div
                  style={{
                    width: '88px',
                    height: '88px',
                    borderRadius: '22px',
                    overflow: 'hidden',
                    background: '#111',
                    border: '3px solid rgba(15,15,20,0.95)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '14px',
                  }}
                >
                  {selectedUser.avatar_path ? (
                    <img
                      src={getPublicAvatarUrl(selectedUser.avatar_path)}
                      alt="avatar user"
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  ) : (
                    <span style={{ fontSize: '30px' }}>👤</span>
                  )}
                </div>

                <div style={{ color: '#fff', fontSize: '22px', fontWeight: 'bold', marginBottom: '4px' }}>
                  {selectedUser.full_name || 'User'}
                </div>

                <div style={{ color: '#aaa', marginBottom: '14px' }}>
                  @{selectedUser.username || 'fara_username'}
                </div>

                <div
                  style={{
                    display: 'flex',
                    gap: '10px',
                    flexWrap: 'wrap',
                    marginBottom: '16px',
                  }}
                >
                  <div
                    style={{
                      ...badgeStyle,
                      color: '#fff',
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(255,255,255,0.14)',
                    }}
                  >
                    Tara: {selectedUser.country || '-'}
                  </div>

                  <div
                    style={{
                      ...badgeStyle,
                      color: 'var(--neon-cyan)',
                      background: 'rgba(0,243,255,0.08)',
                      border: '1px solid rgba(0,243,255,0.20)',
                    }}
                  >
                    Level {selectedUser.level ?? '-'}
                  </div>

                  <div
                    style={{
                      ...badgeStyle,
                      color: 'var(--neon-purple)',
                      background: 'rgba(188,19,254,0.08)',
                      border: '1px solid rgba(188,19,254,0.20)',
                    }}
                  >
                    {selectedUser.total_xp ?? 0} XP
                  </div>

                  <div
                    style={{
                      ...badgeStyle,
                      color: '#00ff99',
                      background: 'rgba(0,255,153,0.08)',
                      border: '1px solid rgba(0,255,153,0.20)',
                    }}
                  >
                    {selectedUser.streak_days ?? 0} zile streak
                  </div>
                </div>

                <div
                  style={{
                    padding: '14px',
                    borderRadius: '12px',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    color: '#ddd',
                    lineHeight: 1.5,
                  }}
                >
                  <strong style={{ color: '#fff' }}>Bio:</strong>{' '}
                  {selectedUser.bio || 'Utilizatorul nu are bio setat.'}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Profile;