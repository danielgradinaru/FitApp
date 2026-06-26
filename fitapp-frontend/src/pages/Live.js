// src/pages/Live.js
import React, { useEffect, useRef, useState } from 'react';
import { FaStop, FaPlay, FaSave, FaTrash } from 'react-icons/fa';
import { useNavigate } from 'react-router-dom';
import { saveResult } from '../api';

const Live = () => {
  const navigate = useNavigate();

  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  const ws = useRef(null);
  const streamRef = useRef(null);
  const reqIdRef = useRef(null);
  const lastSendTime = useRef(0);

  const [exercise, setExercise] = useState('Genuflexiune');
  const [isLive, setIsLive] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const [liveImage, setLiveImage] = useState(null);
  const [repsList, setRepsList] = useState([]);

  const isPlank = exercise === 'Plank';
  const unitLabel = isPlank ? 'evaluări' : 'repetări';
  const singleUnitLabel = isPlank ? 'Evaluare' : 'Rep';

  useEffect(() => {
    return () => {
      console.log('Cleanup: Component Unmount');
      stopLiveSession();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopLiveSession = () => {
    console.log('Stopping Session...');
    setIsLive(false);

    if (reqIdRef.current) {
      cancelAnimationFrame(reqIdRef.current);
      reqIdRef.current = null;
    }

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setLiveImage(null);
    setIsLoading(false);
  };

  const startLive = async () => {
    if (isLoading) return;

    setIsLoading(true);
    console.log('Starting Live Session...');

    try {
      stopLiveSession();

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 30 },
        },
      });

      console.log('Camera access granted');
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;

        await new Promise((resolve) => {
          videoRef.current.onloadedmetadata = () => {
            videoRef.current
              .play()
              .then(resolve)
              .catch((err) => {
                console.error('Play error:', err);
                resolve();
              });
          };
        });
      }

      console.log(`Connecting WS to: ws://localhost:8000/ws/live/${exercise}`);
      ws.current = new WebSocket(`ws://localhost:8000/ws/live/${exercise}`);

      ws.current.onopen = () => {
        console.log('WS Connected');
        setIsLive(true);
        setIsLoading(false);
        sendFrameLoop();
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'FRAME_UPDATE') {
            setLiveImage(`data:image/jpeg;base64,${data.image}`);
            return;
          }

          if (data.type === 'REP_COMPLETE' || data.type === 'REP_DONE') {
            const rep = data.rep_data || data.rep;

            if (rep) {
              setRepsList((prev) => [...prev, rep]);
            }

            return;
          }

          if (data.type === 'ERROR') {
            console.error('Backend error:', data.message);
          }
        } catch (err) {
          console.error('Parse Error:', err);
        }
      };

      ws.current.onerror = (event) => {
        console.error('WS Error:', event);
        setIsLive(false);
        setIsLoading(false);
        alert('Eroare conexiune server. Verifică dacă backend-ul rulează.');
      };

      ws.current.onclose = () => {
        console.log('WS Closed');
        setIsLive(false);
      };
    } catch (err) {
      console.error('Critical Error:', err);
      alert(`Eroare: ${err.message}. Verifică permisiunile camerei.`);
      setIsLoading(false);
      setIsLive(false);
    }
  };

  const sendFrameLoop = () => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) return;

    const now = Date.now();

    // Limitare FPS aproximativ 12 FPS.
    if (now - lastSendTime.current < 80) {
      reqIdRef.current = requestAnimationFrame(sendFrameLoop);
      return;
    }

    lastSendTime.current = now;

    if (videoRef.current && canvasRef.current) {
      const vid = videoRef.current;
      const cvs = canvasRef.current;

      if (vid.readyState === 4 && vid.videoWidth > 0) {
        const scale = 480 / vid.videoWidth;

        cvs.width = 480;
        cvs.height = Math.max(1, Math.round(vid.videoHeight * scale));

        const ctx = cvs.getContext('2d');
        ctx.drawImage(vid, 0, 0, cvs.width, cvs.height);

        const base64Img = cvs.toDataURL('image/jpeg', 0.6);

        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
          ws.current.send(base64Img);
        }
      }
    }

    reqIdRef.current = requestAnimationFrame(sendFrameLoop);
  };

  const handleSaveWorkout = async () => {
    if (repsList.length === 0) {
      alert(
        isPlank
          ? 'Nu există încă o evaluare de plank pentru a salva.'
          : 'Nu ai efectuat nicio repetare corectă pentru a salva.'
      );
      return;
    }

    const totalScore = repsList.reduce((acc, rep) => acc + (Number(rep.score) || 0), 0);
    const avgScore = Math.floor(totalScore / repsList.length);

    try {
      const res = await saveResult({
        exercise,
        avg_score: avgScore,
        reps: repsList,
      });

      const { xp_table, new_level, level_up, badges } = res.data;

      let msg = `🎉 SESIUNE LIVE SALVATĂ!\n\n`;
      msg += `📈 STATISTICI XP:\n`;
      msg += `   • Din ${isPlank ? 'evaluări' : 'repetări'}: +${xp_table?.reps ?? 0} XP\n`;
      msg += `   • Bonus Scor: +${xp_table?.bonus ?? 0} XP\n`;

      if ((xp_table?.streak ?? 0) > 0) {
        msg += `   • 🔥 Bonus Streak: +${xp_table.streak} XP\n`;
      }

      msg += `----------------\nTOTAL CÂȘTIGAT: +${xp_table?.total ?? 0} XP\n`;

      if (level_up) {
        msg += `\n🆙 LEVEL UP! Ai atins nivelul ${new_level}!`;
      }

      if (badges && badges.length > 0) {
        msg += `\n\n🏅 INSIGNE NOI DEBLOCATE:\n${badges.join('\n')}`;
      }

      alert(msg);
      navigate('/history');
    } catch (err) {
      console.error(err);
      alert('Eroare la salvare. Asigură-te că ești logat.');
    }
  };

  const clearSession = () => {
    setRepsList([]);
  };

  return (
    <div
      style={{
        maxWidth: '1200px',
        margin: '0 auto',
        height: '85vh',
        display: 'flex',
        gap: '20px',
      }}
    >
      {/* ZONA VIDEO */}
      <div
        className="cyber-card"
        style={{
          flex: 2,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Video invizibil folosit pentru captura */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={{
            position: 'absolute',
            opacity: 0,
            pointerEvents: 'none',
            width: 1,
            height: 1,
          }}
        />

        <canvas ref={canvasRef} style={{ display: 'none' }} />

        {!isLive ? (
          <div style={{ textAlign: 'center', zIndex: 10 }}>
            <h2
              className="glow-text"
              style={{
                fontFamily: 'Orbitron',
                color: 'var(--neon-green)',
              }}
            >
              MOD LIVE
            </h2>

            <div style={{ marginBottom: '20px' }}>
              <label
                style={{
                  color: '#aaa',
                  display: 'block',
                  marginBottom: '5px',
                }}
              >
                Exercițiu
              </label>

              <select
                className="cyber-input"
                value={exercise}
                onChange={(e) => setExercise(e.target.value)}
                style={{ maxWidth: '300px' }}
                disabled={isLoading}
              >
                <option value="Genuflexiune">Genuflexiune</option>
                <option value="Flotare">Flotare</option>
                <option value="Deadlift">Deadlift</option>
                <option value="Fandare">Fandare</option>
                <option value="Abdomene">Abdomene</option>
                <option value="Tractiuni">Tractiuni</option>
                <option value="Bench Press">Bench Press</option>
                <option value="Biceps Curl">Biceps Curl</option>
                <option value="Mountain Climbers">Mountain Climbers</option>
                <option value="Lateral Raises">Lateral Raises</option>
                <option value="Plank">Plank</option>
              </select>
            </div>

            {repsList.length > 0 && (
              <div
                style={{
                  marginBottom: '20px',
                  padding: '15px',
                  border: '1px solid #333',
                  borderRadius: '8px',
                  background: 'rgba(0,0,0,0.5)',
                }}
              >
                <p style={{ color: '#fff', margin: '0 0 10px 0' }}>
                  Sesiune anterioară: {repsList.length} {unitLabel}
                </p>

                <div
                  style={{
                    display: 'flex',
                    gap: '10px',
                    justifyContent: 'center',
                  }}
                >
                  <button
                    onClick={handleSaveWorkout}
                    className="cyber-btn"
                    style={{
                      borderColor: 'lime',
                      color: 'lime',
                      fontSize: '0.9rem',
                      padding: '8px 15px',
                    }}
                  >
                    <FaSave style={{ marginRight: '5px' }} /> SALVEAZĂ
                  </button>

                  <button
                    onClick={clearSession}
                    className="cyber-btn"
                    style={{
                      borderColor: 'red',
                      color: 'red',
                      fontSize: '0.9rem',
                      padding: '8px 15px',
                    }}
                  >
                    <FaTrash style={{ marginRight: '5px' }} /> ȘTERGE
                  </button>
                </div>
              </div>
            )}

            <button
              onClick={startLive}
              disabled={isLoading}
              className="cyber-btn"
              style={{
                fontSize: '1.2rem',
                padding: '15px 40px',
                opacity: isLoading ? 0.5 : 1,
              }}
            >
              {isLoading ? (
                'SE CONECTEAZĂ...'
              ) : (
                <>
                  <FaPlay style={{ marginRight: '10px' }} /> START CAMERA
                </>
              )}
            </button>
          </div>
        ) : (
          <>
            {/* Display Stream Procesat */}
            {liveImage ? (
              <img
                src={liveImage}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                }}
                alt="Live Analysis"
              />
            ) : (
              <div
                style={{
                  color: '#fff',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                }}
              >
                <div
                  style={{
                    width: '30px',
                    height: '30px',
                    border: '3px solid var(--neon-cyan)',
                    borderTop: '3px solid transparent',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite',
                    marginBottom: '10px',
                  }}
                />
                Se inițializează fluxul AI...
              </div>
            )}

            {/* Buton Stop */}
            <div
              style={{
                position: 'absolute',
                bottom: '20px',
                display: 'flex',
                gap: '20px',
                alignItems: 'center',
              }}
            >
              <div
                style={{
                  background: 'rgba(0,0,0,0.8)',
                  padding: '5px 15px',
                  borderRadius: '8px',
                  border: '1px solid var(--neon-cyan)',
                }}
              >
                <span
                  style={{
                    color: '#fff',
                    fontSize: '20px',
                    fontFamily: 'Orbitron',
                  }}
                >
                  {isPlank ? 'Evaluări' : 'Reps'}: {repsList.length}
                </span>
              </div>

              <button
                onClick={stopLiveSession}
                className="cyber-btn"
                style={{
                  borderColor: 'red',
                  color: 'red',
                  background: 'rgba(0,0,0,0.8)',
                }}
              >
                <FaStop style={{ marginRight: '10px' }} /> STOP
              </button>
            </div>
          </>
        )}
      </div>

      {/* ZONA DREAPTA: LISTA REPETARI / EVALUARI */}
      <div
        className="cyber-card"
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '15px',
            borderBottom: '1px solid #333',
            background: 'rgba(0,255,0,0.05)',
          }}
        >
          <h3
            style={{
              margin: 0,
              fontFamily: 'Orbitron',
              color: 'var(--neon-green)',
              textAlign: 'center',
            }}
          >
            FEEDBACK LIVE
          </h3>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
          {repsList.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                color: '#666',
                marginTop: '40px',
              }}
            >
              <p>{isPlank ? 'Aștept prima evaluare...' : 'Aștept prima repetare...'}</p>
              <small>Asigură-te că tot corpul este în cadru.</small>
            </div>
          ) : (
            [...repsList].reverse().map((rep, idx) => (
              <div
                key={`${rep.id || idx}-${idx}`}
                style={{
                  marginBottom: '15px',
                  background: '#000',
                  borderRadius: '8px',
                  border: '1px solid #333',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    padding: '5px 10px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    background: '#111',
                  }}
                >
                  <span style={{ fontWeight: 'bold', color: '#fff' }}>
                    {singleUnitLabel} #{rep.id || repsList.length - idx}
                  </span>

                  <span
                    style={{
                      color: rep.score >= 80 ? 'lime' : 'orange',
                      fontWeight: 'bold',
                    }}
                  >
                    {rep.score}%
                  </span>
                </div>

                {rep.image && (
                  <img
                    src={rep.image}
                    style={{
                      width: '100%',
                      display: 'block',
                    }}
                    alt={`${singleUnitLabel} Snapshot`}
                  />
                )}

                <ul
                  style={{
                    margin: 0,
                    padding: '10px 10px 10px 25px',
                    fontSize: '0.8rem',
                    color: '#ddd',
                  }}
                >
                  {(rep.feedback || []).map((feedbackItem, i) => (
                    <li key={i}>{feedbackItem}</li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default Live;
